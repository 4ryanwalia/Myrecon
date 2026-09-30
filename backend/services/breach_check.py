"""Incident-scoped results. Never expose the email's unrelated breach history."""
import re
import threading
import time
from urllib.parse import quote

import requests

BASE = "https://api.xposedornot.com/v1"
_catalogue = None
_catalogue_until = 0
_lock = threading.Lock()


def normalise(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def resolve_target(target, catalogue):
    names = {normalise(target.get("name", ""))}
    date = target.get("breach_date", "")
    period = 4 if target.get("match_year") else 7
    matches = [b for b in catalogue if normalise(b.get("breachID", "")) in names
               and b.get("breachedDate", "")[:period] == date[:period]]
    # A name is not an incident when multiple records can fit it. Sensitive or
    # non-searchable records cannot support a negative email result either.
    if len(matches) != 1 or matches[0].get("searchable") is not True or matches[0].get("sensitive") is True:
        return None
    return matches[0]["breachID"]


def _get_json(url):
    response = requests.get(url, headers={"Accept": "application/json", "User-Agent": "MyRecon/1.3"}, timeout=(10, 20))
    if response.status_code == 429:
        raise RuntimeError("rate_limited")
    if response.status_code != 200 or "json" not in response.headers.get("Content-Type", "").lower():
        raise RuntimeError("unavailable")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("unavailable")
    return data


def catalogue():
    global _catalogue, _catalogue_until
    with _lock:
        if _catalogue is not None and time.monotonic() < _catalogue_until:
            return _catalogue
        data = _get_json(BASE + "/breaches")
        rows = data.get("exposedBreaches")
        if not isinstance(rows, list) or not rows or any(not isinstance(b, dict) for b in rows):
            raise RuntimeError("unavailable")
        _catalogue, _catalogue_until = rows, time.monotonic() + 3600
        return rows


def check_incident(email, targets):
    if not targets:
        return {"state": "unsupported", "message": "An email check is not available for this incident. Some events do not have searchable email records."}
    try:
        records = catalogue()
        ids = [resolve_target(t, records) for t in targets]
        if any(i is None for i in ids):
            return {"state": "unsupported", "message": "This exact incident is not available in the provider's searchable records. We cannot tell whether you were affected."}
        data = _get_json(BASE + "/check-email/" + quote(email, safe=""))
        if data.get("Error") == "Not found":
            names = []
        elif data.get("status") == "success" and isinstance(data.get("breaches"), list):
            names = []
            for group in data["breaches"]:
                if not isinstance(group, list) or any(not isinstance(n, str) for n in group):
                    raise RuntimeError("unavailable")
                names.extend(group)
        else:
            raise RuntimeError("unavailable")
        matched = any(i in names for i in ids)
        return {"state": "found" if matched else "not_found", "provider": "XposedOrNot",
                "message": "Your email appears in this breach's records." if matched else
                "No match for your email in this breach's searchable records. This does not prove you were unaffected."}
    except Exception as exc:
        state = "rate_limited" if isinstance(exc, RuntimeError) and str(exc) == "rate_limited" else "unavailable"
        # Do not log request exceptions: the provider URL contains the email.
        return {"state": state, "message": "The breach service is busy. Please try again later." if state == "rate_limited" else
                "We could not complete the check. Please try again. No result was established."}
