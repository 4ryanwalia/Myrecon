"""Bounded anonymous public Maps reviews for source-established Google IDs."""
import os
import re
from urllib.parse import urlsplit

MAX_REVIEWS = 100

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


def enrich_google_reviews(enrichment):
    """Retrieve public contributions only for already source-linked Google IDs.

    Existing public collections win. The opt-in anonymous source supplies
    reviews without paid enrichment or forwarding the operator session.
    Duplicate identities share one result. Two distinct contributors per report
    bound requests, and all source diagnostics survive fallback success.
    """
    from copy import deepcopy
    from modules.email_maps_public import fetch_public_maps_reviews

    profiles = [p for p in enrichment.get("profiles", [])
                if isinstance(p, dict) and p.get("platform") == "Google"]
    sources = enrichment.setdefault("sources", [])
    free_enabled = os.getenv("EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED", "false").lower() == "true"
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
        reported_stats = None
        latest = {"name": "Google Maps public reviews", "provider": "Google public contributions",
                  "status": "disabled", "contributor_id": contributor,
                  "reason": "Public review retrieval is disabled on this backend."}
        if free_enabled:
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

