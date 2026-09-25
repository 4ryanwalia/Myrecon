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
import time

from core import store as _store

MAX_SCANS = 50
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_PROFILE_FIELDS = ("platform", "url", "confidence", "display_name", "bio",
                   "profile_pic_url", "platform_category", "category", "exists")


class NotFound(Exception):
    """No such scan for this user."""


def valid_id(scan_id: str) -> bool:
    return bool(_ID_RE.match(scan_id or ""))


def _trim(result: dict) -> dict:
    results = result.get("results") or {}
    return {
        "status": "ok",
        "query": result.get("query") or {},
        "summary": result.get("summary") or {},
        "coverage": result.get("coverage"),
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


def save(uid: str, result: dict) -> str:
    """Record a finished scan. Returns its id."""
    query = result.get("query") or {}
    summary = result.get("summary") or {}
    scan_id = _store.store.push(f"web/scans/{uid}", _trim(result))
    _store.store.set(f"web/history/{uid}/{scan_id}", {
        "handle": str(query.get("username", ""))[:64],
        "scope": "full" if query.get("scope") == "full" else "standard",
        "at": int(time.time() * 1000),
        "profiles": int(summary.get("profiles", 0) or 0),
        "checked": int(summary.get("checked", 0) or 0),
    })
    _prune(uid)
    return scan_id


def _prune(uid: str) -> None:
    index = _store.store.get(f"web/history/{uid}") or {}
    for old in sorted(index)[:-MAX_SCANS]:
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
    _store.store.delete(f"web/scans/{uid}/{scan_id}")
    _store.store.delete(f"web/history/{uid}/{scan_id}")


def clear(uid: str) -> None:
    _store.store.delete(f"web/scans/{uid}")
    _store.store.delete(f"web/history/{uid}")
