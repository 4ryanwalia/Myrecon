"""Bounded anonymous Google Maps contributions for a source-established ID.

This module cannot resolve an email to a Google identity. It reads one public
contributor response, never cookies, operator sessions or inferred locations.
Google's undocumented array layout may change; unreadable data stays unknown.

Protocol reference (MIT, Copyright 2026 Akshay):
https://github.com/FR46M3N7-P4R71CL3/Account-Lens/blob/main/extension/background.js
The parser and transport below are independently implemented. GHunt's public
Maps helper corroborates the contribution-count layout, not live review support.
"""
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

ENDPOINT = "https://www.google.com/locationhistory/preview/mas"
SOURCE = "Google Maps public contributions"
MAX_BYTES = 2_000_000
MAX_REVIEWS = 100
DEADLINE_SECONDS = 20
_ID = re.compile(r"[0-9]{15,25}\Z")
_CONTRIBUTOR_LINK = re.compile(r"/maps/contrib/([0-9]{15,25})(?:/|[?#]|$)")
_PLACE_ID = re.compile(r"ChIJ[A-Za-z0-9_-]{1,200}\Z")
_REVIEW_ID = re.compile(r"[A-Za-z0-9_-]{1,500}\Z")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Fixed wire-format fields from a public Maps contributor request, not an
# arbitrary provider URL or a query composed from an email/name/local part.
_REVIEW_REQUEST = (
    "!2m3!1skn5natqnEo2v4-EP0fq1gQY!7e81!15i14414!6m2!4b1!7b1"
    "!10m5!1b1!5b1!9m1!1e3!11b1!14m60!1m49!1m5!1m4!1e1!1e3!1e2!1e4"
    "!3m5!2m4!3m3!1m2!1i260!2i365!4m1!3i10!10b1!11m33"
    "!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3"
    "!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2"
    "!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!2m5!1e1!1e4!1e5!1e3!1e2"
    "!3b1!4b1!5m1!1e1!17m28!1m6!1m2!1i0!2i0!2m2!1i530!2i768"
    "!1m6!1m2!1i974!2i0!2m2!1i1024!2i768!1m6!1m2!1i0!2i0"
    "!2m2!1i1024!2i20!1m6!1m2!1i0!2i748!2m2!1i1024!2i768!41m14"
)


def _at(value, *indexes):
    for index in indexes:
        if not isinstance(value, list) or len(value) <= index:
            return None
        value = value[index]
    return value


def _text(value, limit):
    return _CONTROL.sub("", value[:limit]).strip() if isinstance(value, str) else ""


def _number(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) and lower <= value <= upper else None
    except OverflowError:
        return None


def _result(contributor_id, status="unknown", reason="Public review data was not readable."):
    return {"status": status, "reviews": [], "display_name": "", "stats": {},
            "limited": True, "reason": reason, "source": SOURCE,
            "contributor_id": contributor_id if isinstance(contributor_id, str) and _ID.fullmatch(contributor_id) else "",
            "returned": 0, "limit": MAX_REVIEWS}


def _exposed_ids(context):
    """Only explicit identity fields or contributor links; never numeric guesses."""
    stack = [(context, 0)]
    visited = 0
    while stack and visited < 200:
        value, depth = stack.pop()
        visited += 1
        if isinstance(value, str):
            yield from _CONTRIBUTOR_LINK.findall(value[:3000])
        elif depth < 4 and isinstance(value, list):
            stack.extend((item, depth + 1) for item in value[:40])
        elif depth < 4 and isinstance(value, dict):
            for key, item in list(value.items())[:40]:
                if key in ("contributor_id", "gaia_id", "personId") and isinstance(item, str) and _ID.fullmatch(item):
                    yield item
                stack.append((item, depth + 1))


def _utc_date(microseconds):
    if isinstance(microseconds, bool) or not isinstance(microseconds, int):
        return ""
    try:
        stamp = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=microseconds)
        if not datetime(2005, 1, 1, tzinfo=timezone.utc) <= stamp <= datetime.now(timezone.utc):
            return ""
        return stamp.isoformat().replace("+00:00", "Z")
    except (OverflowError, ValueError):
        return ""


def _review(row, contributor_id):
    body, venue = _at(row, 2, 2), _at(row, 4)
    if not isinstance(body, list) or not isinstance(venue, list):
        return None
    name = _text(_at(venue, 2), 300)
    rating = _number(_at(body, 0, 0), 1, 5)
    if rating is not None and int(rating) != rating:
        rating = None
    comment = _text(_at(body, 15, 0, 0), 6000)
    if not name or (rating is None and not comment):
        return None
    review = {"name": name, "source_url": f"https://www.google.com/maps/contrib/{contributor_id}/reviews"}
    address, date = _text(_at(venue, 3), 1000), _utc_date(_at(row, 2, 1, 3))
    if address:
        review["address"] = address
    if date:
        review["date"] = date
    if comment:
        review["text"] = comment
    if rating is not None:
        review["rating"] = int(rating)
    latitude, longitude = _number(_at(venue, 0, 2), -90, 90), _number(_at(venue, 0, 3), -180, 180)
    if latitude is not None and longitude is not None:
        review.update(latitude=latitude, longitude=longitude)
    place_id = _at(row, 1, 0, 1)
    if isinstance(place_id, str) and _PLACE_ID.fullmatch(place_id):
        review["source_url"] = f"https://www.google.com/maps/contrib/{contributor_id}/place/{place_id}"
        review["maps_url"] = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": name, "query_place_id": place_id})
    elif latitude is not None and longitude is not None:
        review["maps_url"] = "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{latitude},{longitude}"})
    review_id = _at(row, 2, 0)
    if isinstance(review_id, str) and _REVIEW_ID.fullmatch(review_id):
        review["id"] = review_id
    else:
        review_id = ""
    return review, review_id


def normalize_public_maps_reviews(payload, contributor_id):
    result = _result(contributor_id)
    if not isinstance(contributor_id, str) or not _ID.fullmatch(contributor_id):
        result["reason"] = "A source-established numeric contributor ID is required."
        return result
    context, section = _at(payload, 16), _at(payload, 45)
    name = _text(_at(context, 0), 300)
    if not isinstance(context, list) or not name:
        result["reason"] = "No readable public contributor context was returned."
        return result
    if any(value != contributor_id for value in _exposed_ids(context)):
        result["reason"] = "Contributor identity did not match the requested ID."
        return result
    if not isinstance(section, list) or not isinstance(_at(section, 0), list):
        result["reason"] = "The public review layout was absent or unreadable; privacy and zero reviews cannot be determined."
        return result
    result["display_name"] = name
    for entry in (_at(context, 8, 0) or [])[:40] if isinstance(_at(context, 8, 0), list) else []:
        label, count = _at(entry, 6), _at(entry, 7)
        if label in ("Reviews", "Ratings", "Photos", "Answers") and isinstance(count, int) and not isinstance(count, bool) and 0 <= count <= 1_000_000_000:
            result["stats"][label] = count
    rows = section[0]
    seen, unreadable = set(), False
    for row in rows[:MAX_REVIEWS]:
        parsed = _review(row, contributor_id)
        if parsed is None:
            unreadable = True
            continue
        review, review_id = parsed
        identity = ("id", review_id) if review_id else ("fields", json.dumps(review, sort_keys=True, ensure_ascii=False))
        if identity in seen:
            continue
        seen.add(identity)
        result["reviews"].append(review)
    result["returned"] = len(result["reviews"])
    stats = result["stats"]
    total = stats["Reviews"] + stats["Ratings"] if "Reviews" in stats and "Ratings" in stats else None
    result["limited"] = bool(_at(section, 1)) or len(rows) >= MAX_REVIEWS or unreadable or total is None or total != result["returned"]
    if not result["returned"] and (rows or total != 0 or result["limited"]):
        result["reason"] = "No readable reviews were returned; this does not establish that no public reviews exist."
        return result
    result["status"] = "partial" if result["limited"] else "ok"
    result["reason"] = "Public reviews and ratings only; the returned set may be incomplete." if result["limited"] else "Readable public contributor response; venue coordinates describe reviewed places."
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def _anonymous_auth(request):
    # A callable auth override also prevents requests from loading .netrc.
    request.headers.pop("Authorization", None)
    request.headers.pop("Cookie", None)
    return request


def read_public_maps_json(response, deadline):
    chunks, size = [], 0
    for chunk in response.iter_content(8192):
        if time.monotonic() > deadline:
            raise TimeoutError("Public source time budget exceeded")
        size += len(chunk)
        if size > MAX_BYTES:
            raise ValueError("Public source response size exceeded")
        chunks.append(chunk)
    if time.monotonic() > deadline:
        raise TimeoutError("Public source time budget exceeded")
    document = b"".join(chunks).decode("utf-8-sig").lstrip()
    if document.startswith(")]}'"):
        document = document[4:].lstrip()
    return json.loads(document, parse_constant=_reject_constant)


def fetch_public_maps_reviews(contributor_id):
    result = _result(contributor_id)
    if not isinstance(contributor_id, str) or not _ID.fullmatch(contributor_id):
        result["reason"] = "A source-established numeric contributor ID is required."
        return result
    response = None
    try:
        deadline = time.monotonic() + DEADLINE_SECONDS
        pb = f"!1s{contributor_id}{_REVIEW_REQUEST}!1i{MAX_REVIEWS}!2m9!2b1!3b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!7m2!1m1!1e1"
        response = requests.get(ENDPOINT, params={"authuser": 0, "hl": "en", "gl": "us", "pb": pb},
                                headers={"Accept": "application/json", "User-Agent": "MyRecon/1.0 public-contributor-lookup"},
                                auth=_anonymous_auth, timeout=(3, 12), allow_redirects=False, stream=True)
        if response.status_code != 200:
            result["status"] = "rate_limited" if response.status_code in (403, 429) else "unavailable"
            result["reason"] = "Public contributor source blocked or rate-limited the request." if result["status"] == "rate_limited" else "Public contributor source did not return a readable successful response."
            return result
        return normalize_public_maps_reviews(read_public_maps_json(response, deadline), contributor_id)
    except (requests.Timeout, TimeoutError):
        result.update(status="timeout", reason="Public contributor source exceeded the lookup time budget.")
    except requests.RequestException:
        result.update(status="unavailable", reason="Public contributor source could not be reached.")
    except (ValueError, TypeError, OverflowError, RecursionError):
        result["reason"] = "Public contributor response was unreadable or exceeded the response limit."
    finally:
        if response is not None:
            response.close()
    return result
