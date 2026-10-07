"""Source-attributed email report, derived only from completed provider findings.

No identifier guessing, extra network calls, credential values or persistence.
Dates describe the source event, never when this person first used the email.
"""
import calendar
import re
from copy import deepcopy
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit


_PLATFORM_ALIASES = {
    "github": "GitHub", "githubcom": "GitHub", "linkedin": "LinkedIn", "linkedincom": "LinkedIn",
    "google": "Google", "googleaccount": "Google", "googlemaps": "Google",
    "twitter": "X", "twittercom": "X", "x": "X", "xcom": "X", "twitterx": "X", "xtwitter": "X",
    "facebook": "Facebook", "facebookcom": "Facebook", "gravatar": "Gravatar", "gravatarcom": "Gravatar",
    "aliexpress": "AliExpress", "spotify": "Spotify", "wordpress": "WordPress", "wix": "Wix", "zoom": "Zoom",
}


def _platform(value):
    name = str(value or "").strip()
    return _PLATFORM_ALIASES.get(re.sub(r"[^a-z0-9]", "", name.lower()), name)


def _profile_url(value):
    """Identity URL, retaining query identifiers and discarding known tracking."""
    try:
        parsed = urlsplit(str(value or ""))
        if parsed.scheme.lower() not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            return ""
        host = parsed.hostname.lower().removeprefix("www.")
        host = {"twitter.com": "x.com"}.get(host, host)
        port = parsed.port
        if port and port not in (80, 443):
            host += ":" + str(port)
        path = parsed.path.rstrip("/")
        if host in ("github.com", "x.com"):
            path = path.lower()
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in
                 {"fbclid", "gclid", "msclkid", "trk", "trackingid", "originalsubdomain"}]
        # A platform home page is a service link, not an account identifier.
        if not path and not query:
            return ""
        return host + path + ("?" + urlencode(sorted(query)) if query else "")
    except (ValueError, TypeError):
        return ""


def _profile_id(profile):
    fields = profile.get("fields") or {}
    value = profile.get("id") or next((fields.get(k) for k in ("ID", "User ID", "Google ID") if fields.get(k)), "")
    return str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ""


def _same_profile(left, right):
    platform = _platform(left.get("platform"))
    if not platform or platform.casefold() != _platform(right.get("platform")).casefold():
        return False
    left_id, right_id = _profile_id(left), _profile_id(right)
    if left_id and right_id:
        return left_id == right_id
    left_url, right_url = _profile_url(left.get("url")), _profile_url(right.get("url"))
    if left_url and right_url:
        return left_url == right_url
    # Only these platforms have account handles in this report. A name or a
    # shared avatar never establishes account identity.
    if platform not in {"GitHub", "LinkedIn", "X", "Facebook", "Gravatar", "Spotify", "AliExpress"}:
        return False
    left_name, right_name = str(left.get("username") or "").strip(), str(right.get("username") or "").strip()
    if platform in {"GitHub", "X"}:
        left_name, right_name = left_name.casefold(), right_name.casefold()
    return bool(left_name and left_name == right_name)


def _same_collection_item(kind, left, right):
    if left == right:
        return True
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if kind == "reviews":
        if left.get("id") and right.get("id"):
            return left["id"] == right["id"]
        required = ("name", "address")
        temporal = ("date", "date_label")
        additional = ("text", "rating")
        if not any(left.get(k) and left.get(k) == right.get(k) for k in temporal) and not (
                left.get("text") and left.get("text") == right.get("text")):
            return False
    elif kind == "positions":
        required, temporal, additional = ("title", "company", "start"), ("end",), ()
    elif kind == "education":
        required, temporal, additional = ("school",), ("start", "end"), ("degree", "field_of_study")
        if not any(left.get(k) and left.get(k) == right.get(k) for k in ("degree", "start")):
            return False
    else:
        return False
    return (all(left.get(k) and left.get(k) == right.get(k) for k in required) and
            all(left.get(k) in (None, "") or right.get(k) in (None, "") or left[k] == right[k]
                for k in temporal + additional))


def _merge_profile(target, incoming):
    """Keep primary association and retain provider provenance and conflicts."""
    primary = {k: target.get(k, "") for k in ("source", "basis")}
    attribution = {k: incoming.get(k, "") for k in ("source", "basis")}
    provenance = {k: incoming.get(k, "") for k in ("source", "basis", "evidence", "evidence_url", "url", "profile_status")}
    if provenance not in target.setdefault("provenance", []):
        target["provenance"].append(provenance)
    if incoming.get("source") and incoming["source"] not in target.setdefault("sources", []):
        target["sources"].append(incoming["source"])

    def merge_mapping(existing, added, prefix=""):
        for field, value in added.items():
            if field in {"platform", "source", "basis", "evidence", "evidence_url", "provenance", "sources", "field_sources", "field_conflicts"}:
                continue
            path = prefix + field
            old = existing.get(field)
            if value is None or value == "" or value == [] or value == {}:
                continue
            if old is None or old == "" or old == [] or old == {}:
                existing[field] = deepcopy(value)
                if attribution != primary:
                    target.setdefault("field_sources", {})[path] = attribution
            elif isinstance(old, dict) and isinstance(value, dict):
                merge_mapping(old, value, path + ".")
            elif isinstance(old, list) and isinstance(value, list):
                for item in value:
                    matched = next((r for r in old if _same_collection_item(field, r, item)), None)
                    if matched is not None and isinstance(matched, dict) and isinstance(item, dict):
                        merge_mapping(matched, item, path + ".")
                    elif matched is None:
                        old.append(deepcopy(item))
            elif old != value:
                if path in {"id", "fields.ID", "fields.User ID", "fields.Google ID"} and str(old) == str(value):
                    continue
                if path == "url" and _profile_url(old) and _profile_url(old) == _profile_url(value):
                    continue  # The original URLs remain in source provenance.
                origin = target.get("field_sources", {}).get(path, primary)
                conflicts = target.setdefault("field_conflicts", {}).setdefault(path, [{"value": deepcopy(old), **origin}])
                alternative = {"value": deepcopy(value), **attribution}
                if alternative not in conflicts:
                    conflicts.append(alternative)
                # Long summaries can be truncated by a source. Preserve both,
                # and show the fuller text without changing association basis.
                if field == "bio" and isinstance(old, str) and isinstance(value, str) and len(value) > len(old):
                    existing[field] = value
                    target.setdefault("field_sources", {})[path] = attribution
                elif field == "profile_status" and value == "ok":
                    existing[field] = value
                    target.setdefault("field_sources", {})[path] = attribution
    merge_mapping(target, incoming)


def _add_profile(profiles, incoming):
    incoming = deepcopy(incoming)
    incoming["platform"] = _platform(incoming.get("platform"))
    matches = [profile for profile in profiles if _same_profile(profile, incoming)]
    target = matches[0] if len(matches) == 1 else None
    if target is None:
        target = incoming
        profiles.append(target)
    _merge_profile(target, incoming)
    return target


def event_date(value):
    raw = str(value or "").strip()
    try:
        if re.fullmatch(r"\d{4}", raw):
            day, precision = date(int(raw), 1, 1), "year"
        elif re.fullmatch(r"\d{4}-\d{2}", raw):
            day, precision = date.fromisoformat(raw + "-01"), "month"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            day, precision = date.fromisoformat(raw), "day"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", raw):
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
            day, precision = stamp.date(), "day"
        else:
            return None
        if day > datetime.now(timezone.utc).date():
            return None
        normalized = day.isoformat()[:{"year": 4, "month": 7, "day": 10}[precision]]
        label = str(day.year) if precision == "year" else f"{calendar.month_abbr[day.month]} {day.year}" if precision == "month" else f"{calendar.month_abbr[day.month]} {day.day}, {day.year}"
        return {"date": normalized, "date_label": label, "precision": precision}
    except (ValueError, OverflowError):
        return None


def _breach_events(row):
    """Group compatible precision without choosing between conflicting dates.

    A year can corroborate a month, and a month can corroborate a day. If a
    coarse date fits two conflicting dates, retain it in both evidence lists;
    it cannot resolve which more precise date is correct.
    """
    dates = row["dates"]
    candidates = [reported for reported in dates if not any(
        other["date"] != reported["date"] and other["date"].startswith(reported["date"] + "-")
        for other in dates)]
    if not candidates:
        return [{"kind": "breach", "title": row["name"] + " breach", "sources": row["sources"],
                 "detail": "Breach date not provided.", "url": "", "date": "",
                 "date_label": "Date not provided", "precision": "unknown", "date_evidence": [],
                 "date_conflict": False}]
    entries = []
    for candidate in candidates:
        evidence = [reported for reported in dates if candidate["date"] == reported["date"] or
                    candidate["date"].startswith(reported["date"] + "-")]
        sources = [source for source in row["sources"] if any(source in e["sources"] for e in evidence)]
        conflicting = len(candidates) > 1
        detail = "Sources report different breach dates." if conflicting else (
            "Most precise reported breach date; source dates are retained." if len(evidence) > 1 else "Reported breach date.")
        entries.append({"kind": "breach", "title": row["name"] + " breach", "sources": sources,
                        "detail": detail, "url": "", **{k: candidate[k] for k in ("date", "date_label", "precision")},
                        "date_evidence": evidence, "date_conflict": conflicting})
    return entries


def build_email_evidence(data):
    profiles, timeline, undated, breaches = [], [], [], {}
    enrichment = data.get("profile_enrichment") or {}
    event_index = {}

    def event(kind, title, raw, source, detail, url="", actor=None):
        row = {"kind": kind, "title": title, "sources": [source], "detail": detail, "url": url}
        parsed = event_date(raw)
        dated = parsed or {"date": "", "date_label": "Date not provided", "precision": "unknown"}
        observation = {"source": source, "date": str(raw or ""), "url": url}
        actor = actor if actor is not None else _profile_url(url)
        identity = (kind, title, dated["date"], dated["precision"], actor) if actor else None
        if identity and identity in event_index:
            existing = event_index[identity]
            if source not in existing["sources"]:
                existing["sources"].append(source)
            if observation not in existing["source_evidence"]:
                existing["source_evidence"].append(observation)
            return
        row = {**row, **dated, "source_evidence": [observation]}
        (timeline if parsed else undated).append(row)
        if identity:
            event_index[identity] = row

    github = data.get("github") or {}
    if github.get("username") and github.get("status", "found") == "found":
        historical = bool(github.get("evidence_url"))
        github_profile = _add_profile(profiles, {"platform": "GitHub", "username": github["username"],
                         "display_name": github.get("display_name", ""), "url": github.get("url", ""),
                         "avatar_url": github.get("avatar_url", ""), "bio": github.get("bio", ""),
                         "location": github.get("location", ""), "company": github.get("company", ""), "fields": github.get("fields", {}),
                         "website": github.get("website", ""), "stats": github.get("stats", {}), "created_at": github.get("created_at", ""),
                         "evidence": github.get("evidence", "Public GitHub email evidence"),
                         "evidence_url": github.get("evidence_url") or github.get("url", ""),
                         "basis": "historical_commit" if historical else "exact_public_email",
                         "source": "GitHub public API", "profile_status": github.get("profile_status", "ok")})
        if github.get("created_at"):
            event("profile", "GitHub profile created", github["created_at"], "GitHub public API",
                  "Creation date of the linked profile; does not date its association with this email.", github.get("url", ""), id(github_profile))
        if github.get("commit_date"):
            event("activity", "Public GitHub commit", github["commit_date"], "GitHub commit search",
                  "Author-supplied commit date with this exact author email. Current ownership is not established.", github.get("evidence_url", ""))

    gravatar = data.get("gravatar") or {}
    if gravatar.get("exists"):
        _add_profile(profiles, {"platform": "Gravatar", "username": gravatar.get("username", ""),
                         "display_name": gravatar.get("display_name", ""), "url": gravatar.get("profile_url", ""),
                         "avatar_url": gravatar.get("avatar_url", ""), "bio": gravatar.get("bio", ""),
                         "location": gravatar.get("location", ""), "stats": {},
                         "evidence": "Public Gravatar profile returned for this exact email hash",
                         "basis": "email_hash", "source": "Gravatar public profile", "profile_status": "ok"})

    for profile in enrichment.get("profiles", []):
        matching = _add_profile(profiles, profile)
        platform = matching["platform"]
        if profile.get("last_seen"):
            event("activity", platform + " last seen", profile["last_seen"], profile["source"],
                  "Last-seen signal reported by this source; it does not establish last use of the email.", profile.get("url", ""), id(matching))
        if profile.get("first_seen"):
            event("activity", platform + " first seen", profile["first_seen"], profile["source"],
                  "First-seen signal reported by this source; coverage may begin after account creation.", profile.get("url", ""), id(matching))
        if profile.get("created_at"):
            event("profile", platform + " profile created", profile["created_at"], profile["source"],
                  "Source-reported profile creation date.", profile.get("url", ""), id(matching))
        for review in profile.get("reviews", []):
            if review.get("date"):
                event("activity", "Review: " + (review.get("name") or "Google Maps venue"), review["date"], review.get("source") or profile.get("review_source") or profile["source"],
                      "Public review date reported by the source.", review.get("source_url", ""),
                      (id(matching), review.get("name", ""), review.get("address", ""), review.get("text", "")))

    def key(name):
        return re.sub(r"[^a-z0-9]", "", re.sub(r"\.(com|net|org|io|co|me|ru|de|fr|uk|in)$", "", str(name or "").strip().lower()))

    for provider, records in (("XposedOrNot analytics", (data.get("darkweb") or {}).get("breaches", [])),
                              ("LeakCheck", (data.get("breaches") or {}).get("sources", [])),
                              ("XposedOrNot fallback", (data.get("fallback") or {}).get("sources", [])),
                              ("LeakCheck Pro", (data.get("breach_details") or {}).get("records", []))):
        for record in records:
            name = record.get("name", "")
            ident = key(name)
            if not ident:
                continue
            row = breaches.setdefault(ident, {"name": name, "dates": [], "sources": []})
            if provider not in row["sources"]:
                row["sources"].append(provider)
            parsed = event_date(record.get("date"))
            if parsed:
                existing = next((d for d in row["dates"] if d["date"] == parsed["date"]), None)
                if existing:
                    if provider not in existing["sources"]:
                        existing["sources"].append(provider)
                else:
                    row["dates"].append({**parsed, "sources": [provider]})
    for row in breaches.values():
        for entry in _breach_events(row):
            (timeline if entry["date"] else undated).append(entry)
    timeline.sort(key=lambda e: (e["date"], e["title"]), reverse=True)
    services = (data.get("linked_services") or {}).get("services", [])
    registration_rows = (data.get("registration_checks") or {}).get("services", []) + enrichment.get("registrations", [])
    registrations = {key(r.get("domain") or r.get("service")) for r in registration_rows if r.get("status") == "found"}
    identity = {field: [{"value": p[field], "source": p["platform"], "url": p["url"], "basis": p["basis"]}
                       for p in profiles if p.get(field)] for field in ("display_name", "username", "location")}
    for row in (data.get("breach_details") or {}).get("records", []):
        for target, field in (("display_name", "full_name"), ("username", "username")):
            if row.get(field):
                value = {"value": row[field], "source": row["name"], "url": "", "basis": "historical_breach"}
                if value not in identity[target]:
                    identity[target].append(value)
    locations = list(identity["location"])
    for p in profiles:
        for review in p.get("reviews", []):
            if review.get("address"):
                coords = (review.get("latitude"), review.get("longitude"))
                maps = review.get("maps_url") or (f"https://www.google.com/maps?q={coords[0]},{coords[1]}" if all(c is not None for c in coords) else "")
                locations.append({"value": review["address"], "source": p["platform"], "basis": "review_venue",
                                  "url": maps, "venue": review.get("name", ""), "date_label": review.get("date_label", ""),
                                  "latitude": coords[0], "longitude": coords[1]})
    found_registrations = {}
    for row in registration_rows:
        if row.get("status") == "found":
            found_registrations.setdefault(key(row.get("domain") or row.get("service")), deepcopy(row))
    from modules.email_quality import annotate_report
    return annotate_report({"version": 2, "profiles": profiles, "identity": identity, "locations": locations,
            "registrations": list(found_registrations.values()), "timeline": timeline,
            "undated_events": undated, "earliest": timeline[-1] if timeline else None,
            "latest": timeline[0] if timeline else None,
            "counts": {"public_profiles": len(profiles), "registration_signals": len(registrations - {""}),
                       "historical_services": sum(r.get("kind") == "breach" for r in services),
                       "named_breaches": len(breaches)},
            "counts_note": "Counts describe returned evidence. Categories can overlap; zero does not prove no account or exposure.",
            "date_note": "Earliest and latest refer only to dated evidence returned by these sources. They are not first or last use of this email.",
            "breach_date_note": "Breach dates describe the reported incident, not when this email was first seen. Compatible source dates are merged at their best reported precision; conflicting dates remain separate. Historical exposure does not establish a current account.",
            "identity_note": "Names and usernames are source-reported. Locations include profile fields and review venues; a reviewed venue is not a home address."})
