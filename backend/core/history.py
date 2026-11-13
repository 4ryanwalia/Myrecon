"""Compatibility API: scan history is no longer collected or served."""
import re
from core import store as _store

class NotFound(Exception):
    pass

def valid_id(scan_id):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,40}", scan_id or ""))

def save(uid, result, scan_id=None, job_token=None):
    return None

def list_scans(uid):
    return []

def get(uid, scan_id):
    raise NotFound()

def delete(uid, scan_id):
    if not valid_id(scan_id):
        raise NotFound()
    _store.store.delete(f"web/scans/{uid}/{scan_id}")
    _store.store.delete(f"web/history/{uid}/{scan_id}")

def clear(uid):
    _store.store.delete(f"web/scans/{uid}")
    _store.store.delete(f"web/history/{uid}")
