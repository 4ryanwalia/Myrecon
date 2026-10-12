"""Optional historical aliases from LeakCheck Pro; credential values excluded."""
import os
import time
from urllib.parse import quote
import requests
from modules.email_enrichment import text
from modules.email_public_profiles import bounded_json


def normalize_breach_details(payload, email):
    if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get("result"), list):
        raise ValueError("Unreadable breach detail response")
    total = payload.get("found")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError("Unreadable breach count")
    records, seen = [], set()
    discarded = 0
    for row in payload["result"][:100]:
        if not isinstance(row, dict) or text(row.get("email")).lower() != email.lower() or not isinstance(row.get("source"), dict):
            discarded += 1
            continue
        source = row["source"]
        name = text(source.get("name"), 160)
        if not name:
            discarded += 1
            continue
        fullname = text(row.get("name"), 300) or " ".join(filter(None, [text(row.get("first_name"), 150), text(row.get("last_name"), 150)]))
        entry = {"name": name, "date": text(source.get("breach_date"), 80), "username": text(row.get("username"), 300),
                 "full_name": fullname, "password_exposed": bool(row.get("password")),
                 "unverified": bool(source.get("unverified")), "compilation": bool(source.get("compilation")),
                 "source": "LeakCheck Pro"}
        fingerprint = tuple(entry.values())
        if fingerprint not in seen:
            seen.add(fingerprint); records.append(entry)
    limited = total > len(payload["result"]) or len(payload["result"]) > 100
    return {"status": "partial" if discarded or limited else "ok", "checked": not bool(discarded or limited),
            "breached": bool(records), "records": records, "reported_rows": total, "truncated": limited,
            "message": "Some breach rows were not returned or could not be attributed to the exact query." if discarded or limited else ""}


def breach_details(email):
    empty = {"records": [], "checked": False, "breached": False}
    token = os.environ.get("LEAKCHECK_APIKEY", "").strip()
    if not token or os.environ.get("EMAIL_BREACH_DETAILS_ENABLED", "false").lower() != "true":
        return {**empty, "status": "unconfigured"}
    response = None
    try:
        deadline = time.monotonic() + 25
        response = requests.get("https://leakcheck.io/api/v2/query/" + quote(email, safe=""),
                                params={"type": "email", "limit": 100, "offset": 0},
                                headers={"X-API-Key": token, "Accept": "application/json"}, timeout=(5, 15), allow_redirects=False, stream=True)
        if response.status_code != 200:
            state = "rate_limited" if response.status_code == 429 else "authentication_required" if response.status_code in (401, 403) else "unavailable"
            return {**empty, "status": state, "message": "Breach detail provider " + state.replace("_", " ") + "; other findings retained."}
        return normalize_breach_details(bounded_json(response, deadline), email)
    except (requests.RequestException, ValueError, TypeError):
        return {**empty, "status": "unavailable", "message": "Breach details unavailable; other findings retained."}
    finally:
        if response is not None:
            response.close()
