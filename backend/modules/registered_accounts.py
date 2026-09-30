"""Bounded process adapter for optional Holehe registration signals.

No email is placed in argv, stored or logged. The separately installed GPL
runtime is pinned; its implementation is not copied into this repository.
"""
import json
from pathlib import Path
import subprocess
import sys
import threading

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "email-account-services.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
_SLOTS = threading.BoundedSemaphore(2)


def result(rows, status="ok"):
    counts = {state: sum(r["status"] == state for r in rows) for state in
              ("found", "no_signal", "unavailable", "rate_limited", "skipped", "timeout")}
    checked = counts["found"] + counts["no_signal"]
    attempted = len(rows) - counts["skipped"]
    return {"status": status, "engine": "Holehe", "source": CATALOG["source"],
            "revision": CATALOG["revision"], "catalogue_count": len(rows),
            "checked": checked, "attempted": attempted, "found": counts["found"],
            "partial": checked < attempted, "counts": counts, "services": rows}


def baseline(status="unavailable"):
    return [{"service": r["name"], "id": r["id"], "domain": r["domain"],
             "method": r["method"], "status": status if r["enabled"] else "skipped",
             "reason": "Registration check unavailable" if r["enabled"] else r["skip_reason"]}
            for r in CATALOG["services"]]


def scan_registered_accounts(email: str) -> dict:
    if not _SLOTS.acquire(blocking=False):
        return result(baseline(), "busy")
    try:
        proc = subprocess.run([sys.executable, str(Path(__file__).with_name("holehe_worker.py"))],
                              input=json.dumps({"email": email}), text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              timeout=42, check=False)
        if proc.returncode != 0:
            return result(baseline(), "unavailable")
        data = json.loads(proc.stdout)
        rows = data.get("services") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) != len(CATALOG["services"]):
            return result(baseline(), "unavailable")
        states = {"found", "no_signal", "unavailable", "rate_limited", "skipped", "timeout"}
        clean = []
        for row, expected in zip(rows, CATALOG["services"]):
            if (not isinstance(row, dict) or row.get("id") != expected["id"]
                    or row.get("status") not in states or not isinstance(row.get("reason"), str)):
                return result(baseline(), "unavailable")
            clean.append({"service": expected["name"], "id": expected["id"],
                          "domain": expected["domain"], "method": expected["method"],
                          "status": row["status"], "reason": row["reason"]})
        # The worker returns only the fixed public service schema, never
        # recovery phone numbers, names, email fragments or provider bodies.
        return result(clean, "ok" if data.get("status", "ok") == "ok" else "unavailable")
    except (subprocess.TimeoutExpired, OSError, ValueError, TypeError):
        return result(baseline("timeout"), "unavailable")
    finally:
        _SLOTS.release()
