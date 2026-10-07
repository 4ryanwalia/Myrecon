"""Google public-profile lookup for Android, independent of account/breach scans.

The operator's GHunt session stays inside the isolated backend worker. Only the
normalized public Google identity and that contributor's public reviews are
returned. This service does not load account plans, save results or probe
registration/recovery endpoints.
"""
from copy import deepcopy
import math
import re
from urllib.parse import urlsplit

from modules.email_ghunt import enrich_ghunt_email
from modules.email_public_profiles import enrich_google_reviews, google_contributor_id


_ID = re.compile(r"[0-9]{15,25}\Z")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_STATES = {"ok", "partial", "found", "no_match", "not_found", "disabled",
           "unconfigured", "authentication_required", "rate_limited", "timeout",
           "unavailable", "unknown", "skipped", "credits_exhausted"}
_SUCCESS = {"ok", "found", "no_match", "not_found"}
_REVIEW_SOURCES = {"Google Maps public contributions", "SerpApi Google Maps contributor reviews",
                   "Google Maps public reviews", "Google public contributions", "SerpApi", "GHunt"}
_REASONS = {
    "ok": "Public source completed.", "found": "Public Google profile returned for the exact email.",
    "partial": "The public review collection may be incomplete.",
    "no_match": "The configured source returned no public Google profile.",
    "not_found": "The configured source returned no public Google profile.",
    "disabled": "The Google source is disabled on this backend.",
    "unconfigured": "The Google source requires backend operator configuration.",
    "authentication_required": "The backend operator must authenticate the Google source.",
    "rate_limited": "The source is busy or has limited this request; try again later.",
    "timeout": "The public source exceeded its lookup time budget.",
    "unavailable": "The public source could not return usable data.",
    "unknown": "The public response was inconclusive; absence cannot be established.",
    "skipped": "This source was not queried.",
    "credits_exhausted": "The configured optional review provider has no available credits.",
}


def _text(value, limit=1000):
    return _CONTROL.sub("", value[:limit]).strip() if isinstance(value, str) else ""


def _state(value):
    return value if isinstance(value, str) and value in _STATES else "unavailable"


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1_000_000_000 else None


def _review_source(value):
    return value if isinstance(value, str) and value in _REVIEW_SOURCES else ""


def _public_url(value, contributor="", avatar=False):
    value = _text(value, 3000)
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port:
            return ""
        if avatar:
            return value if parsed.hostname.endswith(".googleusercontent.com") else ""
        if parsed.hostname not in ("google.com", "www.google.com", "maps.google.com"):
            return ""
        if parsed.path.startswith("/maps/contrib/"):
            match = re.match(r"/maps/contrib/([0-9]{15,25})(?:/|$)", parsed.path)
            return value if match and match.group(1) == contributor else ""
        return value if parsed.path.startswith("/maps/") else ""
    except (ValueError, TypeError):
        return ""


def _review(row, contributor):
    if not isinstance(row, dict):
        return None
    result = {}
    for key, limit in (("id", 500), ("name", 300), ("address", 1000), ("text", 6000),
                       ("date", 80), ("date_label", 100), ("owner_reply", 3000), ("owner_reply_date", 100)):
        value = _text(row.get(key), limit)
        if value:
            result[key] = value
    rating = row.get("rating")
    if isinstance(rating, (int, float)) and not isinstance(rating, bool) and 1 <= rating <= 5 and math.isfinite(rating):
        result["rating"] = rating
    if not result.get("name") or ("rating" not in result and not result.get("text")):
        return None
    result["source_url"] = _public_url(row.get("source_url"), contributor) or f"https://www.google.com/maps/contrib/{contributor}/reviews"
    maps_url = _public_url(row.get("maps_url"), contributor)
    if maps_url:
        result["maps_url"] = maps_url
    return result


def _coverage(row, contributor, returned):
    row = row if isinstance(row, dict) else {}
    state = _state(row.get("status", "unknown"))
    result = {"status": state, "contributor_id": contributor, "returned": returned,
              "source": _review_source(row.get("source")), "reason": _REASONS[state],
              "limited": row.get("limited") is not False, "limit": 100}
    for key in ("total_reported", "ratings_reported", "contributions_reported"):
        result[key] = _count(row.get(key))
    if state == "ok" and result["limited"]:
        result.update(status="partial", reason=_REASONS["partial"])
    return result


def _profile(row):
    if not isinstance(row, dict):
        return None
    try:
        contributor = google_contributor_id(row)
    except (ValueError, TypeError, AttributeError):
        return None
    if not contributor:
        return None
    fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
    if fields.get("ID") and str(fields["ID"]) != contributor:
        return None
    stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
    result = {"platform": "Google", "url": f"https://www.google.com/maps/contrib/{contributor}/reviews",
              "display_name": _text(row.get("display_name"), 300),
              "avatar_url": _public_url(row.get("avatar_url"), avatar=True),
              "fields": {"ID": contributor}, "stats": {}, "reviews": [],
              "source": "GHunt", "basis": "provider_email", "profile_status": "ok",
              "evidence": "An exact-email Google lookup returned this public contributor profile. Profile edits do not establish online activity.",
              "review_source": _review_source(row.get("review_source"))}
    edited = _text(fields.get("Last profile edit"), 80)
    if edited:
        result["fields"]["Last profile edit"] = edited
    for key in ("Reviews", "Ratings", "Photos", "Answers"):
        value = _count(stats.get(key))
        if value is not None:
            result["stats"][key] = value
    rows = row.get("reviews") if isinstance(row.get("reviews"), list) else []
    for review in rows[:100]:
        projected = _review(review, contributor)
        if projected:
            result["reviews"].append(projected)
    result["review_coverage"] = _coverage(row.get("review_coverage"), contributor, len(result["reviews"]))
    # A rejected or truncated record makes the projected collection incomplete.
    if len(result["reviews"]) != len(rows) and result["review_coverage"]["status"] in _SUCCESS:
        result["review_coverage"].update(status="partial", limited=True, reason=_REASONS["partial"])
    return result


def _source(row):
    if not isinstance(row, dict):
        return None
    state = _state(row.get("status"))
    provider = row.get("provider")
    if provider not in ("GHunt", "SerpApi", "Google public contributions"):
        provider = "Google public contributions" if row.get("name") == "Google Maps public reviews" else "GHunt"
    result = {"name": "Google public profile" if provider == "GHunt" else "Google Maps public reviews",
              "provider": provider, "status": state, "reason": _REASONS[state]}
    contributor = row.get("contributor_id")
    if isinstance(contributor, str) and _ID.fullmatch(contributor):
        result["contributor_id"] = contributor
    for key in ("returned", "limit"):
        value = _count(row.get(key))
        if value is not None:
            result[key] = min(value, 100)
    if isinstance(row.get("limited"), bool):
        result["limited"] = row["limited"]
    return result


def lookup_public_profiles(email):
    """Return a bounded public Google projection without other email fanout."""
    try:
        identity = enrich_ghunt_email(email)
        if not isinstance(identity, dict) or not isinstance(identity.get("profiles"), list) or not isinstance(identity.get("sources"), list):
            raise ValueError("Invalid normalized identity result")
    except Exception:
        identity = {"profiles": [], "sources": [{"provider": "GHunt", "status": "unavailable"}]}
    # Project before review retrieval, so unexpected fields cannot reach callers
    # or influence the public review reader. Retain this copy on reader failure.
    profiles = [profile for row in identity["profiles"][:2] if (profile := _profile(row)) is not None]
    sources = [source for row in identity["sources"][:10] if (source := _source(row)) is not None]
    enrichment = {"profiles": profiles, "sources": sources}
    try:
        candidate = enrich_google_reviews(deepcopy(enrichment))
        if not isinstance(candidate, dict) or not isinstance(candidate.get("profiles"), list) or not isinstance(candidate.get("sources"), list):
            raise ValueError("Invalid normalized reviews result")
        enrichment = candidate
    except Exception:
        enrichment["sources"].append({"name": "Google Maps public reviews", "provider": "Google public contributions", "status": "unavailable"})
        for profile in enrichment["profiles"]:
            profile["review_coverage"] = {"status": "unavailable", "limited": True}
    profiles = [profile for row in enrichment["profiles"][:2] if (profile := _profile(row)) is not None]
    sources = [source for row in enrichment["sources"][:20] if (source := _source(row)) is not None]
    if profiles:
        complete = all(profile["review_coverage"]["status"] == "ok" for profile in profiles)
        status = "ok" if complete and all(source["status"] in _SUCCESS for source in sources) else "partial"
    elif sources and all(source["status"] in ("no_match", "not_found") for source in sources):
        status = "no_match"
    else:
        status = next((source["status"] for source in sources if source["status"] not in _SUCCESS), "unavailable")
    return {"query": {"email": email}, "status": status, "profiles": profiles, "sources": sources}
