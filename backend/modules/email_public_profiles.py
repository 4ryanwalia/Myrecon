"""Optional public contributor reviews, only after a source establishes the ID.

This is not an email-to-Google identity resolver. No inferred handles, cookies,
login scraping, arbitrary outbound URLs, retries or raw provider responses.
"""
import json
import os
import re
import time
from urllib.parse import urlsplit

import requests

MAX_BYTES = 2_000_000
MAX_REVIEWS = 100


def bounded_json(response, deadline=None):
    """Bound decoded bytes and elapsed time; socket read timeout bounds waits.

    Callers pass a deadline established before the request so time waiting for
    headers counts too. The deadline is checked between reads, not a watchdog.
    """
    chunks, size = [], 0
    body_deadline = time.monotonic() + 20
    deadline = min(deadline, body_deadline) if deadline is not None else body_deadline
    if time.monotonic() > deadline:
        raise ValueError("Provider response exceeds time limit")
    for chunk in response.iter_content(8192):
        size += len(chunk)
        if size > MAX_BYTES:
            raise ValueError("Provider response exceeds size limit")
        if time.monotonic() > deadline:
            raise ValueError("Provider response exceeds time limit")
        chunks.append(chunk)
    return json.loads(b"".join(chunks))


def google_contributor_id(profile):
    if profile.get("platform") != "Google" or profile.get("basis") != "provider_email" or profile.get("profile_status") != "ok":
        return ""
    raw_url = profile.get("url", "")
    try:
        parsed = urlsplit(raw_url)
        if parsed.scheme == "https" and parsed.hostname in ("www.google.com", "google.com", "maps.google.com") and not parsed.username and not parsed.password:
            match = re.fullmatch(r"/maps/contrib/(\d{15,25})(?:/(?:reviews|photos))?/?", parsed.path)
            if match:
                return match.group(1)
    except (ValueError, TypeError):
        pass
    fields = profile.get("fields", {})
    value = str(fields.get("ID", "")) if isinstance(fields, dict) else ""
    return value if re.fullmatch(r"\d{15,25}", value) else ""


def normalize_google_reviews(payload, contributor_id):
    from modules.email_enrichment import REVIEW_FIELDS, records, text, url
    if not isinstance(payload, dict) or payload.get("error") or payload.get("search_metadata", {}).get("status") != "Success":
        raise ValueError("Unsuccessful contributor response")
    params = payload.get("search_parameters", {})
    if not isinstance(params, dict) or str(params.get("contributor_id", "")) != contributor_id:
        raise ValueError("Contributor identity mismatch")
    reviews = payload.get("reviews", [])
    if not isinstance(reviews, list):
        raise ValueError("Invalid reviews")
    result = []
    for review in reviews[:MAX_REVIEWS]:
        if not isinstance(review, dict):
            continue
        place = review.get("place_info", {})
        place = place if isinstance(place, dict) else {}
        gps = place.get("gps_coordinates", {})
        gps = gps if isinstance(gps, dict) else {}
        reply = review.get("response", {})
        reply = reply if isinstance(reply, dict) else {}
        result.extend(records([{"name": place.get("title"), "address": place.get("address"),
                                "latitude": gps.get("latitude"), "longitude": gps.get("longitude"),
                                "text": review.get("snippet"), "rating": review.get("rating"),
                                "date_label": review.get("date"), "source_url": review.get("link"),
                                "owner_reply": reply.get("snippet"), "owner_reply_date": reply.get("date")}], REVIEW_FIELDS))
    contributor = payload.get("contributor", {})
    contributor = contributor if isinstance(contributor, dict) else {}
    contributions = contributor.get("contributions", {})
    contributions = contributions if isinstance(contributions, dict) else {}
    stats = {k.title(): contributions[k] for k in ("reviews", "ratings", "answers", "photos")
             if isinstance(contributions.get(k), int) and not isinstance(contributions[k], bool) and contributions[k] >= 0}
    expected = stats.get("Reviews", 0) + stats.get("Ratings", 0)
    return {"reviews": result, "display_name": text(contributor.get("name")),
            "avatar_url": url(contributor.get("thumbnail")), "stats": stats,
            "limited": len(reviews) >= MAX_REVIEWS or expected > len(result)}


def _enrich_google_reviews_serpapi(enrichment):
    """Mutates a normalized enrichment result; at most one bounded API request."""
    token = os.getenv("SERPAPI_API_KEY", "").strip()
    enabled = os.getenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "false").lower() == "true"
    profiles = enrichment.get("profiles", [])
    google = next((p for p in profiles if p.get("platform") == "Google"), None)
    if google is None or google.get("reviews"):
        return enrichment
    source = {"name": "Google Maps public reviews", "provider": "SerpApi", "status": "unconfigured"}
    enrichment.setdefault("sources", []).append(source)
    if not enabled or not token:
        source["reason"] = "Optional contributor review retrieval requires EMAIL_GOOGLE_REVIEWS_ENABLED=true and SERPAPI_API_KEY."
        return enrichment
    contributor_id = google_contributor_id(google)
    if not contributor_id:
        source.update(status="unknown", reason="No source-linked Google contributor ID was returned.")
        return enrichment
    response = None
    try:
        deadline = time.monotonic() + 20
        response = requests.get("https://serpapi.com/search.json", params={"engine": "google_maps_contributor_reviews",
                                "contributor_id": contributor_id, "api_key": token, "num": MAX_REVIEWS, "hl": "en"},
                                timeout=(3, 12), allow_redirects=False, stream=True)
        if response.status_code != 200:
            source["status"] = {401: "authentication_required", 403: "authentication_required", 429: "rate_limited"}.get(response.status_code, "unavailable")
            return enrichment
        details = normalize_google_reviews(bounded_json(response, deadline), contributor_id)
        google["reviews"] = details["reviews"]
        google["review_source"] = "SerpApi Google Maps contributor reviews"
        google["review_limit"] = MAX_REVIEWS
        google["review_coverage"] = {"total_reported": details["stats"].get("Reviews"),
                                    "ratings_reported": details["stats"].get("Ratings")}
        google.setdefault("stats", {}).update(details["stats"])
        for field in ("display_name", "avatar_url"):
            if not google.get(field):
                google[field] = details[field]
        source.update(status="partial" if details["limited"] else "ok", returned=len(details["reviews"]),
                      limit=MAX_REVIEWS, reason="Public contributor results only; unavailable or additional reviews may be omitted.")
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        source.update(status="unavailable", reason="Contributor source could not return a verified readable response.")
    finally:
        if response is not None:
            response.close()
    return enrichment


def enrich_google_reviews(enrichment):
    """Retrieve public contributions only for already source-linked Google IDs.

    Existing provider collections win. The documented optional SerpApi source
    runs first when configured; an opt-in anonymous source can fill its gap.
    Duplicate identities share one result. Two distinct contributors per report
    bound requests, and all source diagnostics survive fallback success.
    """
    from copy import deepcopy
    from modules.email_maps_public import fetch_public_maps_reviews

    profiles = [p for p in enrichment.get("profiles", [])
                if isinstance(p, dict) and p.get("platform") == "Google"]
    sources = enrichment.setdefault("sources", [])
    free_enabled = os.getenv("EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED", "false").lower() == "true"
    paid_enabled = (os.getenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "false").lower() == "true"
                    and bool(os.getenv("SERPAPI_API_KEY", "").strip()))
    results = {}

    def coverage(profile, state, contributor, source, reason="", limited=False, reported_stats=None):
        stats = profile.get("stats", {}) if reported_stats is None else reported_stats
        count = stats.get("Reviews") if isinstance(stats, dict) else None
        count = count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None
        ratings = stats.get("Ratings") if isinstance(stats, dict) else None
        ratings = ratings if isinstance(ratings, int) and not isinstance(ratings, bool) and ratings >= 0 else None
        returned = len(profile.get("reviews", []))
        reported_minimum = (count or 0) + (ratings or 0)
        limited = limited or reported_minimum > returned
        if limited and state == "ok":
            state = "partial"
        return {"status": state, "contributor_id": contributor, "returned": len(profile.get("reviews", [])),
                "total_reported": count, "ratings_reported": ratings,
                "contributions_reported": count + ratings if count is not None and ratings is not None else None,
                "source": source, "reason": reason,
                "limited": limited, "limit": MAX_REVIEWS}

    def merge_stats(profile, incoming, source):
        target = profile.setdefault("stats", {})
        for name, value in incoming.items():
            if name not in target:
                target[name] = value
            elif target[name] != value:
                alternatives = profile.setdefault("field_conflicts", {}).setdefault("stats." + name,
                    [{"value": target[name], "source": profile.get("source", ""), "basis": profile.get("basis", "")}])
                observation = {"value": value, "source": source, "basis": "public_contributor"}
                if observation not in alternatives:
                    alternatives.append(observation)

    for profile in profiles[:20]:
        contributor = google_contributor_id(profile)
        if profile.get("reviews"):
            profile.setdefault("review_coverage", coverage(profile, "partial" if profile.get("review_limit") and len(profile["reviews"]) >= profile["review_limit"] else "ok",
                               contributor, profile.get("review_source") or profile.get("source", ""),
                               "Only contribution records returned by this source are shown."))
            continue
        if not contributor:
            profile["review_coverage"] = coverage(profile, "unknown", "", "Google Maps public reviews",
                                                   "No source-linked Google contributor ID was returned.")
            sources.append({"name": "Google Maps public reviews", **profile["review_coverage"]})
            continue
        if contributor in results:
            for key, value in results[contributor].items():
                if key == "stats":
                    merge_stats(profile, value, results[contributor].get("review_source", "Google Maps public reviews"))
                elif key != "review_coverage":
                    profile[key] = deepcopy(value)
            previous = results[contributor]["review_coverage"]
            profile["review_coverage"] = deepcopy(previous)
            continue
        if len(results) >= 2:
            profile["review_coverage"] = coverage(profile, "skipped", contributor, "Google Maps public reviews",
                                                   "This report's two-contributor retrieval limit was reached.")
            sources.append({"name": "Google Maps public reviews", **profile["review_coverage"]})
            continue
        local = {"profiles": [profile], "sources": []}
        reported_stats = None
        if paid_enabled or not free_enabled:
            _enrich_google_reviews_serpapi(local)
            for row in local["sources"]:
                row["contributor_id"] = contributor
            sources.extend(local["sources"])
            if "review_coverage" in profile:
                reported_stats = {"Reviews": profile["review_coverage"].get("total_reported"),
                                  "Ratings": profile["review_coverage"].get("ratings_reported")}
        latest = local["sources"][-1] if local["sources"] else {}
        if not profile.get("reviews") and latest.get("status") != "ok" and free_enabled:
            details = fetch_public_maps_reviews(contributor)
            profile["reviews"] = details["reviews"]
            merge_stats(profile, details.get("stats", {}), details["source"])
            reported_stats = details.get("stats", {})
            if not profile.get("display_name") and details.get("display_name"):
                profile["display_name"] = details["display_name"]
            profile["review_source"] = details["source"]
            latest = {"name": "Google Maps public reviews", "provider": "Google public contributions",
                      "status": details["status"], "contributor_id": contributor,
                      "reason": details.get("reason", ""), "returned": len(details["reviews"]),
                      "limit": MAX_REVIEWS, "limited": details.get("limited", False)}
            sources.append(latest)
        profile["review_coverage"] = coverage(profile, latest.get("status", "unconfigured"), contributor,
                                               profile.get("review_source") or latest.get("provider", "Google Maps public reviews"),
                                               latest.get("reason", ""), latest.get("limited", latest.get("status") == "partial"), reported_stats)
        results[contributor] = {key: deepcopy(profile[key]) for key in
                               ("reviews", "stats", "review_source", "review_coverage") if key in profile}
        if reported_stats is not None:
            results[contributor]["stats"] = deepcopy(reported_stats)
    return enrichment


def normalize_linkedin(payload, email):
    """PDL is an aggregated dataset, not a live LinkedIn account verification."""
    from modules.email_enrichment import EDUCATION_FIELDS, POSITION_FIELDS, records, text, url
    if not isinstance(payload, dict) or payload.get("status") != 200:
        raise ValueError("Invalid enrichment response")
    data = payload.get("data")
    likelihood = payload.get("likelihood")
    if not isinstance(data, dict) or not isinstance(likelihood, int) or isinstance(likelihood, bool) or not 6 <= likelihood <= 10 or not isinstance(payload.get("matched"), list) or "email" not in payload["matched"]:
        return None
    addresses = [data.get("work_email")]
    addresses += data.get("personal_emails") if isinstance(data.get("personal_emails"), list) else []
    addresses += [r.get("address") for r in data.get("emails", []) if isinstance(r, dict)] if isinstance(data.get("emails"), list) else []
    if email.strip().lower() not in [a.strip().lower() for a in addresses if isinstance(a, str)]:
        return None
    link = text(data.get("linkedin_url"), 3000)
    if link.startswith(("linkedin.com/", "www.linkedin.com/")):
        link = "https://" + link
    parsed = urlsplit(url(link))
    if parsed.scheme != "https" or parsed.hostname not in ("linkedin.com", "www.linkedin.com") or not re.fullmatch(r"/in/[^/?#]+/?", parsed.path):
        return None
    positions, education = [], []
    for row in data.get("experience", [])[:100] if isinstance(data.get("experience"), list) else []:
        if not isinstance(row, dict):
            continue
        company, title = row.get("company"), row.get("title")
        company = company if isinstance(company, dict) else {}
        title = title if isinstance(title, dict) else {}
        positions.extend(records([{"company": company.get("name"), "title": title.get("name"),
                                   "start": row.get("start_date"), "end": row.get("end_date"),
                                   "description": row.get("summary")}], POSITION_FIELDS))
    for row in data.get("education", [])[:100] if isinstance(data.get("education"), list) else []:
        if not isinstance(row, dict):
            continue
        school = row.get("school")
        school = school if isinstance(school, dict) else {}
        join = lambda v: ", ".join(text(x, 100) for x in v[:10] if isinstance(x, str)) if isinstance(v, list) else ""
        education.extend(records([{"school": school.get("name"), "degree": join(row.get("degrees")),
                                   "field_of_study": join(row.get("majors")), "start": row.get("start_date"),
                                   "end": row.get("end_date"), "description": row.get("summary")}], EDUCATION_FIELDS))
    fields = {"Headline": text(data.get("job_title"))} if data.get("job_title") else {}
    connections = data.get("linkedin_connections")
    if isinstance(connections, int) and not isinstance(connections, bool) and connections >= 0:
        fields["Connections"] = str(connections)
    return {"platform": "LinkedIn", "url": link, "username": text(data.get("linkedin_username")),
            "display_name": text(data.get("full_name")), "bio": text(data.get("summary"), 6000), "avatar_url": "",
            "location": ", ".join(filter(None, [text(data.get(k)) for k in ("location_locality", "location_region", "location_country")])),
            "positions": positions, "education": education, "reviews": [], "fields": fields, "stats": {}, "lists": {},
            "source": "People Data Labs", "basis": "provider_email", "profile_status": "ok",
            "evidence": "Provider dataset associates this LinkedIn profile with the exact queried email; this is not live account verification."}


def enrich_linkedin_email(email):
    """One bounded, credential-gated exact-email enrichment call."""
    source = {"name": "LinkedIn", "provider": "People Data Labs", "status": "unconfigured"}
    result = {"status": "unconfigured", "profiles": [], "registrations": [], "sources": [source]}
    token = os.getenv("PDL_API_KEY", "").strip()
    if os.getenv("EMAIL_LINKEDIN_ENRICHMENT_ENABLED", "false").lower() != "true" or not token:
        source["reason"] = "Optional LinkedIn enrichment requires EMAIL_LINKEDIN_ENRICHMENT_ENABLED=true and PDL_API_KEY."
        return result
    response = None
    try:
        deadline = time.monotonic() + 20
        response = requests.get("https://api.peopledatalabs.com/v5/person/enrich", headers={"X-Api-Key": token},
                                params={"email": email, "min_likelihood": 6, "include_if_matched": "true", "required": "linkedin_url",
                                        "data_include": "full_name,linkedin_url,linkedin_username,linkedin_connections,summary,job_title,location_locality,location_region,location_country,experience,education,emails.address,work_email,personal_emails"},
                                timeout=(3, 12), allow_redirects=False, stream=True)
        if response.status_code != 200:
            source["status"] = {401: "authentication_required", 403: "authentication_required", 402: "credits_exhausted", 404: "no_match", 429: "rate_limited"}.get(response.status_code, "unavailable")
        else:
            profile = normalize_linkedin(bounded_json(response, deadline), email)
            source["status"] = "found" if profile else "unknown"
            source["reason"] = "Provider dataset association; exact email checked." if profile else "Provider response did not establish the exact queried email association."
            if profile:
                result["profiles"].append(profile)
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        source["status"] = "unavailable"
    finally:
        if response is not None:
            response.close()
    result["status"] = "ok" if source["status"] in ("found", "no_match") else source["status"]
    return result
