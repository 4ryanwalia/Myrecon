"""One-time removal of legacy scan storage. Never reads scan payloads."""
import logging
import threading
import time
from core import store as storage

MARKER = "web/metadata/no_scan_storage_v1"
SCAN_PATHS = ("web/history", "web/scans", "web/scan_dispatch", "web/scan_job_data",
              "web/scan_dispatch_signal", "web/match_choices")
_state = "pending"
_lock = threading.Lock()
_started = False
log = logging.getLogger("myrecon.privacy")


def status():
    return _state


def run():
    global _state
    if storage.store.backend != "rtdb":
        _state = "not_configured"
        return
    if storage.store.get(MARKER):
        _state = "complete"
        return
    for path in SCAN_PATHS:
        storage.store.delete(path)
    # Account IDs only, fetched shallowly; scan contents are never downloaded.
    for uid in storage.store.keys("web/users"):
        def minimize(cur):
            if not isinstance(cur, dict):
                return cur
            if not (cur.get("extended") or cur.get("pro") or cur.get("subscription")):
                cur.pop("email", None)
                cur.pop("name", None)
            return cur
        storage.store.transaction(f"web/users/{uid}", minimize)
    storage.store.set(MARKER, {"complete": True})
    _state = "complete"


def ensure_started():
    global _started
    with _lock:
        if _started:
            return
        _started = True
    def work():
        global _state
        for attempt in range(3):
            try:
                run()
                return
            except Exception as exc:
                _state = "retrying"
                log.warning("Legacy storage cleanup failed (%s)", type(exc).__name__)
                time.sleep(10)
        _state = "failed"
    threading.Thread(target=work, name="privacy-cleanup", daemon=True).start()
