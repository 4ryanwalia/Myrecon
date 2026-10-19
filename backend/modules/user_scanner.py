"""Bounded optional adapter; only registry IDs can reach the bundled worker.

Disabled by default. Callers must retain their existing entitlement and scan
limit gates. A request cannot enable an entry or supply Python paths.
"""
import json
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

from modules.user_scanner_registry import (
    REGISTRY, STATES, MAX_MODULES, MAX_OUTPUT, SCAN_SECONDS, MODULE_SECONDS, outcome,
)

_SLOTS = threading.BoundedSemaphore(2)
_WORKER = Path(__file__).with_name("user_scanner_worker.py").resolve()


def _valid_target(target, scan_type):
    if not isinstance(target, str) or len(target) > 254:
        return False
    if scan_type == "username":
        return re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", target) is not None
    return re.fullmatch(r"[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+", target) is not None


def _run_one(spec, target, seconds):
    # A file avoids an unbounded stdout pipe. The bundled worker emits at most
    # MAX_OUTPUT bytes, and the parent reads only MAX_OUTPUT + 1.
    with tempfile.TemporaryFile() as output:
        try:
            proc = subprocess.Popen(
                [sys.executable, "-I", str(_WORKER)], stdin=subprocess.PIPE,
                stdout=output, stderr=subprocess.DEVNULL, cwd=str(_WORKER.parents[1]),
            )
        except OSError:
            return outcome(spec, "unavailable", "Optional worker could not start")
        try:
            proc.communicate(json.dumps({"id": spec.id, "target": target}).encode(), timeout=seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return outcome(spec, "timeout", "Optional module reached its deadline")
        except OSError:
            proc.kill()
            proc.communicate()
            return outcome(spec, "unavailable", "Optional worker communication failed")
        output.seek(0)
        raw = output.read(MAX_OUTPUT + 1)
    if proc.returncode or len(raw) > MAX_OUTPUT:
        return outcome(spec, "unavailable", "Optional worker output was unavailable or exceeded its limit")
    try:
        row = json.loads(raw)
        if (not isinstance(row, dict) or row.get("id") != spec.id
                or row.get("status") not in STATES or not isinstance(row.get("reason"), str)
                or len(row["reason"]) > 256):
            raise ValueError("invalid result")
        # Worker URLs are derived from the target, never upstream metadata.
        expected_url = ("https://github.com/" + target if spec.id == "username.github"
                        else "https://en.gravatar.com/" + hashlib.md5(target.strip().lower().encode()).hexdigest())
        code = row.get("status_code", 0)
        return outcome(spec, row["status"], row["reason"], metadata=row.get("metadata"),
                       url=expected_url if row["status"] == "found" else "",
                       status_code=code if type(code) is int and 0 <= code <= 599 else 0)
    except (ValueError, TypeError, UnicodeError):
        return outcome(spec, "unavailable", "Optional worker returned an invalid result")


def scan_selected(target, scan_type, module_ids=None, *, permitted=False):
    """Internal API only; IDs and permission come from a gated service caller.

    None selects the small registry for this scan type, including skipped rows.
    Unknown/duplicate IDs and excessive selections fail closed before execution.
    """
    if scan_type not in ("username", "email"):
        raise ValueError("Unsupported scan type")
    ids = tuple(module_ids) if module_ids is not None else tuple(
        key for key, spec in REGISTRY.items() if spec.scan_type == scan_type)
    if (len(ids) > MAX_MODULES or any(not isinstance(key, str) for key in ids)
            or len(set(ids)) != len(ids)
            or any(key not in REGISTRY or REGISTRY[key].scan_type != scan_type for key in ids)):
        raise ValueError("Only unique allowlisted module IDs for this scan type are accepted")
    deadline = time.monotonic() + SCAN_SECONDS
    rows = []
    for key in ids:
        spec = REGISTRY[key]
        if permitted is not True or not spec.enabled:
            rows.append(outcome(spec, "skipped", "Optional module is not enabled for this scan"))
        elif not _valid_target(target, scan_type):
            rows.append(outcome(spec, "skipped", "Target is unsupported by this module"))
        elif time.monotonic() >= deadline:
            rows.append(outcome(spec, "timeout", "Optional scan reached its deadline"))
        elif not _SLOTS.acquire(blocking=False):
            rows.append(outcome(spec, "unavailable", "Optional worker capacity is occupied"))
        else:
            try:
                rows.append(_run_one(spec, target, min(MODULE_SECONDS, deadline - time.monotonic())))
            except (OSError, ValueError):
                rows.append(outcome(spec, "unavailable", "Optional worker resources are unavailable"))
            finally:
                _SLOTS.release()
    counts = {state: sum(row["status"] == state for row in rows) for state in STATES}
    partial = any(counts[state] for state in ("unavailable", "rate_limited", "timeout"))
    return {"engine": "User Scanner adapter", "status": "partial" if partial else "ok" if any(
        row["status"] != "skipped" for row in rows) else "skipped",
        "partial": partial, "counts": counts, "checks": rows}


def username_contract(report):
    """Sweep's three verdicts plus exact optional-source status/reason."""
    checks, profiles = [], []
    for row in report["checks"]:
        state = row["status"]
        check = {**row, "verdict": state if state in ("found", "not_found") else "unknown",
                 "unreachable": state in ("unavailable", "rate_limited", "timeout")}
        checks.append(check)
        if state == "found":
            profiles.append({**check, **row["metadata"], "display_name": row["metadata"].get("name", ""),
                             "exists": True, "verified": True,
                             "category": "profile", "platform_category": row["category"],
                             "confidence": "high"})
    return {"platform_checks": checks, "profiles": profiles}


def email_contract(report):
    profiles = [{"platform": row["platform"], "url": row["url"], "source": row["source"],
                 "basis": "email_hash", "profile_status": "ok", "fields": row["metadata"],
                 **row["metadata"],
                 "evidence": row["reason"]} for row in report["checks"] if row["status"] == "found"]
    return {"profiles": profiles, "registrations": [],
            "sources": [{**row, "name": row["platform"]} for row in report["checks"]]}
