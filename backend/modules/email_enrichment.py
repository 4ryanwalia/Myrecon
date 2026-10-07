"""Optional server-side OSINT Industries adapter. Never substitutes sandbox data.

Only the documented spec_format envelope is consumed. Raw responses, passwords,
tokens and cookies are never forwarded. Platform-specific collections are bounded
and projected onto display fields; absent fields remain absent.
"""
import math
import os
import re
import time
from datetime import datetime
from urllib.parse import urlsplit

import requests


def text(value, limit=2000):
    return str(value)[:limit] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def url(value):
    value = text(value, 3000)
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def scalar(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return text(value)


def source_date(value):
    """Provider spec datetimes can omit a zone; keep their reported calendar day."""
    value = text(value, 80)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?", value):
        try:
            datetime.fromisoformat(value)
            return value[:10]
        except ValueError:
            return value
    return value


def key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def records(value, fields):
    """Known aliases only; no raw nested metadata reaches exports."""
    result = []
    for row in value[:100] if isinstance(value, list) else []:
        if not isinstance(row, dict):
            continue
        normalized = {key(k): v for k, v in row.items()}
        projected = {}
        for target, aliases in fields.items():
            v = next((normalized[key(a)] for a in aliases if key(a) in normalized), None)
            if target.endswith("url"):
                v = url(v)
            elif target == "current":
                if not isinstance(v, bool):
                    continue
            elif target in ("latitude", "longitude", "rating"):
                try:
                    v = float(v)
                    lo, hi = {"latitude": (-90, 90), "longitude": (-180, 180), "rating": (0, 5)}[target]
                    if not math.isfinite(v) or not lo <= v <= hi:
                        continue
                except (TypeError, ValueError):
                    continue
            else:
                v = scalar(v)
            if v is not None and v != "":
                projected[target] = v
        if projected:
            result.append(projected)
    return result


REVIEW_FIELDS = {
    "name": ["name", "place_name", "title", "business_name"], "address": ["address", "formatted_address"],
    "text": ["text", "comment", "review_text"], "rating": ["rating", "stars"],
    "date": ["date", "published_at", "timestamp"], "date_label": ["relative_date", "date_label", "date"],
    "latitude": ["latitude", "lat"], "longitude": ["longitude", "lng", "lon"],
    "source_url": ["source_url", "review_url", "url", "link"], "maps_url": ["maps_url", "place_url"],
    "owner_reply": ["owner_reply", "response_text"], "owner_reply_date": ["owner_reply_date", "response_date"],
}
POSITION_FIELDS = {"title": ["title", "job_title", "position"], "company": ["company", "company_name"],
                   "start": ["start", "start_date"], "end": ["end", "end_date"], "current": ["current", "is_current"],
                   "url": ["url", "company_url"], "logo_url": ["logo_url", "company_logo", "company_logo_url"],
                   "location": ["location"], "description": ["description"]}
EDUCATION_FIELDS = {"school": ["school", "school_name", "name"], "degree": ["degree", "field_of_study"],
                    "field_of_study": ["field_of_study"], "description": ["description"],
                    "start": ["start", "start_date"], "end": ["end", "end_date"], "url": ["url", "school_url"],
                    "logo_url": ["logo_url", "school_logo", "school_logo_url"]}


def nested_records(value, fields):
    """Project known public presentation shapes without forwarding raw metadata."""
    prepared = []
    for row in value[:100] if isinstance(value, list) else []:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        if fields is REVIEW_FIELDS:
            location = row.get("location")
            if isinstance(location, dict):
                for target, source in (("name", "name"), ("address", "address"), ("maps_url", "link")):
                    if target not in row:
                        row[target] = location.get(source)
                position = location.get("position")
                if isinstance(position, dict):
                    for coord in ("latitude", "longitude"):
                        if coord not in row:
                            row[coord] = position.get(coord)
        else:
            for target in ("start", "end"):
                year, month = row.get(target + "_year"), row.get(target + "_month")
                if target not in row and isinstance(year, int) and not isinstance(year, bool) and 1000 <= year <= 9999:
                    row[target] = str(year)
                    if isinstance(month, int) and not isinstance(month, bool) and 1 <= month <= 12:
                        row[target] += "-" + str(month).zfill(2)
        prepared.append(row)
    return records(prepared, fields)


def normalize_response(payload, email):
    if not isinstance(payload, list):
        raise ValueError("Expected module results")
    profiles, registrations, sources = [], [], []
    for module in payload[:300]:
        if not isinstance(module, dict) or not isinstance(module.get("module"), str):
            raise ValueError("Invalid module result")
        name = module["module"][:100]
        name = {"google": "Google", "github": "GitHub", "linkedin": "LinkedIn", "aliexpress": "AliExpress", "facebook": "Facebook", "wordpress": "WordPress", "wix": "Wix", "zoom": "Zoom", "twitter": "X", "spotify": "Spotify"}.get(name.lower(), name)
        state = module.get("status", "unknown")
        # Chained pivots are not presented as exact queried-email evidence.
        if str(module.get("query", "")).strip().lower() != email.lower():
            continue
        source = {"name": name, "status": text(state, 40), "provider": "OSINT Industries"}
        sources.append(source)
        if module.get("reliable_source") is False:
            source["status"] = "unknown"
            source["reason"] = "Provider marked this association as unreliable."
            continue
        if state != "found":
            continue
        specs = module.get("spec_format", [])
        if not isinstance(specs, list):
            raise ValueError("Invalid spec format")
        for spec in specs[:20]:
            if not isinstance(spec, dict):
                continue
            values = {key(k): v.get("value") for k, v in spec.items() if isinstance(v, dict)}
            if values.get("breach") is True:
                continue  # Breach names and profile names are different evidence.
            if values.get("registered") is True:
                registrations.append({"service": name, "status": "found", "source": "OSINT Industries", "reason": "Provider registration signal for the queried email"})
            variables = spec.get("platform_variables", [])
            for v in variables[:100] if isinstance(variables, list) else []:
                if isinstance(v, dict):
                    values[key(v.get("key", v.get("proper_key", "")))] = v.get("value")
            get = lambda *aliases: next((values[key(a)] for a in aliases if key(a) in values), None)
            fields = {}
            for label, aliases in {
                "ID": ["id", "user_id", "gaia_id"], "Email": ["email"], "Enterprise user": ["enterprise_user", "is_enterprise"],
                "Connections": ["connections", "connection_count"], "Account count": ["account_count"],
                "Email verified": ["email_verified"], "Blocked": ["blocked", "is_blocked"],
                "Headline": ["headline", "current_position"],
            }.items():
                value = scalar(get(*aliases))
                if value != "":
                    fields[label] = value
            lists = {}
            for label, aliases in {"Auth methods": ["auth_methods", "authentication_providers"], "Active Google apps": ["active_google_apps", "apps", "reachable_apps"]}.items():
                value = get(*aliases)
                if isinstance(value, list):
                    lists[label] = [text(v, 100) for v in value[:30] if text(v, 100)]
            profile = {"platform": name, "username": text(get("username")), "display_name": text(get("name", "display_name")),
                       "url": url(get("profile_url")), "avatar_url": url(get("picture_url", "avatar_url")),
                       "bio": text(get("bio"), 6000), "location": text(get("location", "country")),
                       "website": url(get("website")), "fields": fields, "lists": lists, "stats": {},
                       "last_seen": source_date(get("last_seen", "last_seen_date")), "created_at": source_date(get("creation_date", "created_at")),
                       "first_seen": source_date(get("first_seen", "first_seen_date")),
                       "reviews": nested_records(get("google_reviews", "maps_reviews", "reviews"), REVIEW_FIELDS),
                       "positions": nested_records(get("linkedin_positions", "positions", "experience"), POSITION_FIELDS),
                       "education": nested_records(get("linkedin_education", "education"), EDUCATION_FIELDS),
                       "source": "OSINT Industries", "basis": "provider_email", "profile_status": "ok",
                       "evidence": "Provider returned this profile for the exact queried email; association is source-reported."}
            for label, aliases in {"Reviews": ["reviews_count", "review_count"], "Ratings": ["ratings_count", "rating_count"], "Answers": ["answers_count", "answer_count"], "Followers": ["followers"], "Following": ["following"]}.items():
                v = get(*aliases)
                if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                    profile["stats"][label] = v
            google_stats = get("google_stats")
            if name == "Google" and isinstance(google_stats, dict):
                for stat in ("reviews", "ratings", "answers", "photos"):
                    v = google_stats.get(stat)
                    if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                        profile["stats"][stat.title()] = v
            if not profile["display_name"]:
                profile["display_name"] = " ".join(filter(None, (text(get("first_name")), text(get("last_name")))))
            # A bare registration flag is not a detailed profile.
            if any(profile[k] for k in ("username", "display_name", "url", "avatar_url", "bio", "location", "fields", "lists", "stats", "reviews", "positions", "education")):
                profiles.append(profile)
    incomplete = not sources or any(s["status"] not in ("found", "not_found", "no_match") for s in sources)
    return {"status": "partial" if incomplete else "ok", "profiles": profiles, "registrations": registrations, "sources": sources}


def _enrich_osint_industries(email):
    from modules.email_public_profiles import bounded_json
    empty = {"profiles": [], "registrations": [], "sources": []}
    token = os.environ.get("OSINT_INDUSTRIES_API_KEY", "").strip()
    enabled = os.environ.get("EMAIL_ENRICHMENT_ENABLED", "false").lower() == "true"
    if not token or not enabled:
        return {**empty, "status": "unconfigured", "sources": [{"name": "OSINT Industries", "status": "unconfigured"}],
                "message": "Google reviews and LinkedIn details need EMAIL_ENRICHMENT_ENABLED=true and OSINT_INDUSTRIES_API_KEY; missing access is not evidence of an absent profile."}
    response = None
    try:
        # Provider's minimum processing window is 25s; allow 20s beyond it.
        deadline = time.monotonic() + 45
        response = requests.post("https://api.osint.industries/v2/request",
                                 json={"type": "email", "query": email, "timeout": 25, "premium": False},
                                 headers={"api-key": token, "Accept": "application/json"}, timeout=(5, 35), allow_redirects=False, stream=True)
        if response.status_code != 200:
            state = {401: "authentication_required", 402: "credits_exhausted", 429: "rate_limited"}.get(response.status_code, "unavailable")
            return {**empty, "status": state, "sources": [{"name": "OSINT Industries", "status": state}],
                    "message": "Profile provider " + state.replace("_", " ") + "; other findings retained."}
        result = normalize_response(bounded_json(response, deadline), email)
        return result
    except (requests.RequestException, ValueError, TypeError):
        return {**empty, "status": "unavailable", "sources": [{"name": "OSINT Industries", "status": "unavailable"}],
                "message": "Profile provider could not return readable results; other findings retained."}
    finally:
        if response is not None:
            response.close()


def enrich_email(email):
    from concurrent.futures import ThreadPoolExecutor
    from modules.email_public_profiles import enrich_linkedin_email, enrich_google_reviews
    from modules.email_ghunt import enrich_ghunt_email
    # Independent sources overlap; failure of one retains completed evidence.
    def safe(call, name):
        try:
            response = call(email)
            if (isinstance(response, dict) and isinstance(response.get("profiles"), list)
                    and isinstance(response.get("sources"), list)):
                return response
        except Exception:
            pass  # Never return exception text containing email or authentication data.
        return {"profiles": [], "sources": [{"name": name, "status": "unavailable"}]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        oi = pool.submit(safe, _enrich_osint_industries, "OSINT Industries")
        pdl = pool.submit(safe, enrich_linkedin_email, "People Data Labs")
        google = pool.submit(safe, enrich_ghunt_email, "GHunt")
        result = oi.result()
        linkedin, ghunt = pdl.result(), google.result()
    result.setdefault("registrations", [])
    # Independent opt-in provider remains usable without an OSINT Industries key.
    result["sources"].extend(linkedin["sources"])
    result["profiles"].extend(linkedin["profiles"])
    result["sources"].extend(ghunt["sources"])
    result["profiles"].extend(ghunt["profiles"])
    # Review provider can use a GHunt-established ID without OSINT Industries.
    try:
        result = enrich_google_reviews(result)
    except Exception:
        result["sources"].append({"name": "Google Maps public reviews", "status": "unavailable"})
    return summarize_enrichment(result)


def summarize_enrichment(result):
    """Recompute coverage after independent or URL-based enrichment steps."""
    completed = {"ok", "found", "not_found", "no_match"}
    attempted = [s for s in result["sources"] if s.get("status") not in ("unconfigured", "disabled", "skipped")]
    failures = [s for s in attempted if s.get("status") not in completed]
    if failures and (result["profiles"] or any(s.get("status") in completed for s in attempted)):
        result["status"] = "partial"
        result["message"] = "Some profile sources could not complete; available profiles and source diagnostics are retained."
    elif failures:
        # Preserve useful specific failure codes, while never reporting ok/unconfigured.
        result["status"] = failures[0].get("status", "unavailable")
        if result["status"] not in ("authentication_required", "credits_exhausted", "rate_limited", "unavailable"):
            result["status"] = "unavailable"
        result["message"] = "Configured profile sources could not establish a completed result; see source diagnostics."
    elif result["profiles"] and any(s.get("status") == "unconfigured" for s in result["sources"]):
        result["status"] = "partial"
        result["message"] = "Available profile sources returned; other optional sources remain unconfigured."
    elif attempted:
        result["status"] = "ok"
        result.pop("message", None)
    return result
