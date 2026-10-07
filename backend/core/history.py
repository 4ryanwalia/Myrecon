"""
Scan history for signed-in users.

Every username scan a signed-in user runs, standard or Pro, is kept so they
can reopen it later without scanning again. Guests have no history on the
server; their recent lookups stay in their own browser as before.

Two nodes per scan, so the list stays cheap:
  /web/history/<uid>/<id>   summary: handle, scope, time, counts  (listed)
  /web/scans/<uid>/<id>     the result itself, trimmed            (opened)

Only the newest MAX_SCANS are kept; older ones are deleted as new ones land.
The result is trimmed before it is stored: found profiles, the platforms worth
checking by hand, coverage and the headline numbers. The rejected list (the
400-odd "not here" rows of a Pro scan) is dropped, since it is the bulk of the
payload and says nothing the counts do not.

Like the rest of /web, none of this is readable by a client directly: the
database rules deny it, and the API only ever returns a user's own scans.
"""

import re
import threading
import time

from core import store as _store

MAX_SCANS = 50
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_PROFILE_FIELDS = ("platform", "url", "confidence", "display_name", "bio",
                   "profile_pic_url", "platform_category", "category", "exists")
_USER_LOCKS = tuple(threading.RLock() for _ in range(64))


class NotFound(Exception):
    """No such scan for this user."""


def valid_id(scan_id: str) -> bool:
    return bool(_ID_RE.match(scan_id or ""))


def _user_lock(uid):
    # A fixed number of stripes avoids retaining a lock for every past user.
    return _USER_LOCKS[hash(uid) % len(_USER_LOCKS)]


def _current_job_report(uid, scan_id, result_token):
    from core import scan_jobs
    job = scan_jobs.get(scan_id)
    return (isinstance(job, dict) and job.get("status") == "complete"
            and job.get("uid") == uid and job.get("result_token") == result_token)


def _trim(result: dict) -> dict:
    results = result.get("results") or {}
    return {
        "status": "ok",
        "query": result.get("query") or {},
        "summary": result.get("summary") or {},
        "coverage": result.get("coverage"),
        "partial": bool(result.get("partial")),
        "errors": result.get("errors") or [],
        "results": {
            "profiles": [{k: p[k] for k in _PROFILE_FIELDS if p.get(k) is not None}
                         for p in (results.get("profiles") or [])][:300],
            "documents": [],
            "mentions": [{k: p[k] for k in _PROFILE_FIELDS if p.get(k) is not None}
                         for p in (results.get("mentions") or [])][:100],
        },
        "unverified": (result.get("unverified") or [])[:200],
        "exposures": result.get("exposures") or [],
        "rejected": [],
    }


def save(uid: str, result: dict, scan_id=None, job_token=None) -> str | None:
    """Record a scan, or skip a deterministic job report already deleted."""
    with _user_lock(uid):
        if scan_id is not None and not valid_id(scan_id):
            raise ValueError("Invalid scan id")
        if job_token is not None:
            if scan_id is None or not _current_job_report(uid, scan_id, job_token):
                return None
        query = result.get("query") or {}
        summary = result.get("summary") or {}
        if scan_id is None:
            scan_id = _store.store.push(f"web/scans/{uid}", _trim(result))
        else:
            _store.store.set(f"web/scans/{uid}/{scan_id}", _trim(result))
        _store.store.set(f"web/history/{uid}/{scan_id}", {
            "handle": str(query.get("username", ""))[:64],
            "scope": query.get("scope") if query.get("scope") in ("full", "extended") else "standard",
            "at": int(time.time() * 1000),
            "profiles": int(summary.get("profiles", 0) or 0),
            "checked": int(summary.get("checked", 0) or 0),
        })
        if job_token is not None and not _current_job_report(uid, scan_id, job_token):
            # Cover deletion from another server process too: it publishes the
            # tombstone before deleting nodes, so either it or this guard wins.
            _store.store.delete(f"web/scans/{uid}/{scan_id}")
            _store.store.delete(f"web/history/{uid}/{scan_id}")
            return None
        _prune(uid)
        return scan_id


def _prune(uid: str) -> None:
    index = _store.store.get(f"web/history/{uid}") or {}
    for old in sorted(index, key=lambda key: (index[key] or {}).get("at", 0))[:-MAX_SCANS]:
        delete(uid, old)


def list_scans(uid: str) -> list:
    index = _store.store.get(f"web/history/{uid}") or {}
    rows = [{"id": k, **v} for k, v in index.items() if isinstance(v, dict)]
    rows.sort(key=lambda r: r.get("at", 0), reverse=True)
    return rows


def get(uid: str, scan_id: str) -> dict:
    if not valid_id(scan_id):
        raise NotFound()
    data = _store.store.get(f"web/scans/{uid}/{scan_id}")
    if not isinstance(data, dict):
        raise NotFound()
    return data


def delete(uid: str, scan_id: str) -> None:
    if not valid_id(scan_id):
        raise NotFound()
    with _user_lock(uid):
        from core import scan_jobs
        scan_jobs.erase_history(uid, scan_id)
        _store.store.delete(f"web/scans/{uid}/{scan_id}")
        _store.store.delete(f"web/history/{uid}/{scan_id}")


def clear(uid: str) -> None:
    with _user_lock(uid):
        from core import scan_jobs
        scan_jobs.erase_history(uid)
        _store.store.delete(f"web/scans/{uid}")
        _store.store.delete(f"web/history/{uid}")
