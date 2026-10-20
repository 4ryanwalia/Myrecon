"""Durable presence records for the manually started Colab workers.

The scan queue records a lease only while a job is running.  That cannot say
whether an otherwise idle Colab runtime is still connected, so worker presence
lives in its own RTDB branch.  This module accepts only server timestamps and
states derived from authenticated worker actions.
"""
import hmac
import re
import time

import config
from core import store as storage
from core import scan_jobs


ROOT = "web/scan_workers"
_INSTANCE_ID = re.compile(r"^[A-Za-z0-9_-]{16,80}$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,39}$")
_LIVE_STATES = {"idle", "busy", "recovering"}
_CATALOGUES = {"standard": ("standard", False), "standard:deep": ("standard", True),
               "full": ("full", False), "extended": ("extended", False)}


def validate_worker_id(worker_id):
    if not isinstance(worker_id, str) or not _INSTANCE_ID.fullmatch(worker_id):
        raise ValueError("Invalid worker id")
    return worker_id


def validate_label(label):
    # Older notebook bundles did not send a label.  Keep them compatible while
    # new numbered notebooks identify themselves in the operator console.
    if label in (None, ""):
        return "Colab worker"
    if not isinstance(label, str):
        raise ValueError("Invalid worker label")
    label = label.strip()
    if not _LABEL.fullmatch(label):
        raise ValueError("Invalid worker label")
    return label


def _touch(worker_id, state, label=None, versions=None):
    worker_id = validate_worker_id(worker_id)
    if state not in _LIVE_STATES | {"stopped"}:
        raise ValueError("Invalid worker state")
    now = time.time()

    def change(current):
        current = current or {}
        prior = current.get(worker_id) or {}
        current[worker_id] = {
            "label": validate_label(label if label is not None else prior.get("label")),
            "first_seen_at": prior.get("first_seen_at", now),
            "last_seen_at": now,
            "state": state,
        }
        # Keep only validated catalogue hashes, never arbitrary worker data.
        catalogues = versions if versions is not None else prior.get("catalogues")
        if isinstance(catalogues, dict):
            current[worker_id]["catalogues"] = {
                key: value for key, value in catalogues.items()
                if key in _CATALOGUES and isinstance(value, str)
                and re.fullmatch(r"[a-f0-9]{64}", value)
            }
        if state == "stopped":
            current[worker_id]["stopped_at"] = now
        return current

    storage.store.transaction(ROOT, change)


def seen_claim(worker_id, label, job, versions=None):
    _touch(worker_id, "busy" if job else "idle", label, versions)


def seen_busy(worker_id):
    _touch(worker_id, "busy")


def seen_recovering(worker_id):
    _touch(worker_id, "recovering")


def stopped(worker_id):
    _touch(worker_id, "stopped")


def worker_id_for(job):
    """Return the Colab instance assigned to a lease, if this is one."""
    executor = (job or {}).get("executor", "")
    if not isinstance(executor, str) or not executor.startswith("colab:"):
        return None
    worker_id = executor.split(":", 1)[1]
    try:
        return validate_worker_id(worker_id)
    except ValueError:
        return None


def _state(record, now):
    last_seen = record.get("last_seen_at")
    if not isinstance(last_seen, (int, float)):
        return "offline", None
    age = max(0, int(now - last_seen))
    stored = record.get("state")
    if stored == "stopped":
        return "stopped", age
    if age <= config.SCAN_WORKER_FRESH_SECONDS:
        return stored if stored in _LIVE_STATES else "idle", age
    if age <= config.SCAN_WORKER_OFFLINE_SECONDS:
        return "unreachable", age
    return "offline", age


def status():
    """Return a redacted, label-level status snapshot for an operator.

    Several Colab runtimes can carry the same human label briefly after a
    restart.  Prefer a fresh live instance over an older stopped/stale one and
    expose only a duplicate warning, never job identities or scan data.
    """
    now = time.time()
    records = storage.store.get(ROOT) or {}
    groups = {}
    for worker_id, record in records.items():
        if not isinstance(worker_id, str) or not isinstance(record, dict):
            continue
        try:
            label = validate_label(record.get("label"))
        except ValueError:
            continue
        current, age = _state(record, now)
        groups.setdefault(label, []).append((record, current, age))

    workers = []
    for label, entries in groups.items():
        # A fresh live record is more useful than a newer stopped record from a
        # duplicate tab.  Within the same class, pick the most recently seen.
        def rank(entry):
            record, current, _ = entry
            last_seen = record.get("last_seen_at")
            live = current in _LIVE_STATES
            return live, last_seen if isinstance(last_seen, (int, float)) else 0

        record, current, age = max(entries, key=rank)
        fresh_instances = sum(state in _LIVE_STATES for _, state, _ in entries)
        catalogue_hashes = record.get("catalogues")
        compatibility = {}
        if isinstance(catalogue_hashes, dict):
            compatibility = {
                key.replace(":", "_"): catalogue_hashes.get(key) == scan_jobs.engine_fingerprint(*settings)
                for key, settings in _CATALOGUES.items()
            }
        compatible = all(compatibility.values()) if compatibility else None
        if current == "idle" and compatibility and not any(compatibility.values()):
            current = "incompatible"
        worker = {
            "label": label,
            "state": current,
            "available": current in _LIVE_STATES and compatible is not False,
            "last_seen_at": int(record.get("last_seen_at", 0) or 0),
            "age_seconds": age if age is not None else 0,
            "duplicate": fresh_instances > 1,
        }
        if compatible is not None:
            worker.update(compatible=compatible, compatible_scopes=compatibility)
        workers.append(worker)
    workers.sort(key=lambda worker: worker["label"].casefold())
    return {
        "observed_at": int(now),
        "fresh_after_seconds": config.SCAN_WORKER_FRESH_SECONDS,
        "offline_after_seconds": config.SCAN_WORKER_OFFLINE_SECONDS,
        "workers": workers,
    }


def status_access(token):
    expected = config.SCAN_WORKER_STATUS_TOKEN
    if len(expected) < 32:
        return "unconfigured"
    if isinstance(token, str) and hmac.compare_digest(token, expected):
        return "allowed"
    return "denied"


def status_authenticated(token):
    return status_access(token) == "allowed"


def operator_access(user):
    expected = config.SCAN_WORKER_OPERATOR_EMAIL.strip().casefold()
    if not expected:
        return "unconfigured"
    actual = (user or {}).get("email", "")
    if not isinstance(actual, str):
        return "denied"
    return "allowed" if hmac.compare_digest(actual.strip().casefold(), expected) else "denied"


def operator_allowed(user):
    return operator_access(user) == "allowed"


def launcher_url():
    value = config.SCAN_WORKER_LAUNCHER_URL.strip()
    return value if value.startswith("https://") else ""


def prune():
    cutoff = time.time() - config.SCAN_WORKER_RETENTION_SECONDS

    def change(current):
        current = current or {}
        return {
            worker_id: record for worker_id, record in current.items()
            if isinstance(record, dict) and isinstance(record.get("last_seen_at"), (int, float))
            and record["last_seen_at"] >= cutoff
        }

    storage.store.transaction(ROOT, change)
