"""Distinct email-associated platforms and the coverage behind their evidence.

This projection makes no requests. Historical, source-reported, registration
and owner-declared evidence remain distinct; a returned match is not proof of
an active account or present email ownership.
"""
import re


_ALIASES = {
    "google": ("google", "Google"), "googleaccount": ("google", "Google"),
    "googlepublicprofile": ("google", "Google"), "googlemaps": ("google", "Google"),
    "mapsgoogle": ("google", "Google"), "gmail": ("google", "Google"),
    "googlemail": ("google", "Google"), "youtube": ("google", "Google"),
    "github": ("github", "GitHub"), "gravatar": ("gravatar", "Gravatar"),
    "linkedin": ("linkedin", "LinkedIn"), "linkedinpublicprofile": ("linkedin", "LinkedIn"),
    "x": ("twitter", "X"), "twitter": ("twitter", "X"),
    "twitterx": ("twitter", "X"), "xtwitter": ("twitter", "X"),
    "wordpress": ("wordpress", "WordPress"), "facebook": ("facebook", "Facebook"),
    "instagram": ("instagram", "Instagram"), "spotify": ("spotify", "Spotify"),
    "aliexpress": ("aliexpress", "AliExpress"), "wix": ("wix", "Wix"),
    "zoom": ("zoom", "Zoom"),
}
_HISTORICAL = {"historical_commit", "historical_breach", "historical_public_link"}
_DECLARED = {"owner_declared", "public_link", "historical_public_link"}
_LINKED = {"exact_public_email", "email_hash", "provider_email", "registration_signal"}
_SKIPPED = {"skipped", "disabled", "unconfigured"}
_AUXILIARY = {"openpgp", "openpgpkey", "keysopenpgp", "pgp"}


def canonical_platform(value):
    """Use the same identifier for known names, domains and service aliases."""
    name = value.strip()[:100] if isinstance(value, str) else ""
    token = re.sub(r"\.(com|net|org|io|co|me|ru|de|fr|uk|in)$", "", name.lower().removeprefix("www."))
    token = re.sub(r"[^a-z0-9]", "", token)
    return _ALIASES.get(token, (token, name))


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _text(value, limit=1000):
    return value[:limit] if isinstance(value, str) else ""


def _check_state(value):
    if value == "found":
        return "found"
    if value in ("not_found", "no_match"):
        return "not_found"
    if value in _SKIPPED:
        return "skipped"
    # Holehe's no_signal, errors, blocks and partial replies are inconclusive.
    return "unknown"


def build_platform_summary(data):
    from modules.email_lookup import _COMPILATION
    account_checks = data.get("account_checks") or {}
    enabled = account_checks.get("enabled", False) is True
    enrichment = data.get("profile_enrichment") or {}
    report = data.get("evidence_report") or {}
    rows, checks, source_rows = {}, {}, []

    def platform(name, domain=""):
        ident, label = canonical_platform(name)
        domain_ident, domain_label = canonical_platform(domain)
        if domain_ident in _ALIASES:
            ident, label = domain_ident, domain_label
        if not ident or ident in _AUXILIARY:
            return None
        row = rows.setdefault(ident, {"id": ident, "name": label, "domain": "", "url": "",
                                      "basis": [], "kinds": [], "sources": [],
                                      "evidence": [], "checks": []})
        if domain and not row["domain"]:
            row["domain"] = _text(domain, 253)
        return row

    def evidence(name, kind, basis, source="", detail="", url="", domain=""):
        row = platform(name, domain)
        if row is None:
            return
        item = {"kind": kind, "basis": basis, "source": _text(source, 100),
                "detail": _text(detail), "url": _text(url, 3000)}
        if item not in row["evidence"]:
            row["evidence"].append(item)
        for field, value in (("basis", basis), ("kinds", kind), ("sources", item["source"])):
            if value and value not in row[field]:
                row[field].append(value)
        if item["url"] and (not row["url"] or basis in _LINKED):
            row["url"] = item["url"]

    def check(name, status, source, domain="", reason="", provider=""):
        row = platform(name, domain)
        if row is None:
            return
        state = _check_state(status)
        checks.setdefault(row["id"], set()).add(state)
        item = {"source": _text(source, 100), "status": state,
                "source_status": _text(status, 40), "reason": _text(reason)}
        if provider:
            item["provider"] = _text(provider, 100)
        if item not in row["checks"]:
            row["checks"].append(item)

    profiles = _rows(report.get("profiles", []))
    for profile in profiles:
        provenance = _rows(profile.get("provenance", []))
        primary = {field: profile.get(field, "") for field in ("basis", "source", "evidence", "url")}
        for observation in [primary, *provenance]:
            basis = _text(observation.get("basis"), 80)
            evidence(profile.get("platform", ""), "profile", basis,
                     observation.get("source", ""), observation.get("evidence", ""),
                     observation.get("url") or profile.get("url", ""))
        check(profile.get("platform", ""), "found", profile.get("source", "Public profile"))

    for service in _rows((data.get("linked_services") or {}).get("services", [])):
        kind = service.get("kind", "")
        basis = service.get("basis") or ("historical_breach" if kind == "breach" else
                                         "registration_signal" if kind == "registration" else
                                         "email_hash" if canonical_platform(service.get("service"))[0] == "gravatar" else "")
        evidence(service.get("service", ""), kind, basis, service.get("source", ""),
                 service.get("evidence", ""), service.get("url", ""), service.get("domain", ""))
        for historical in _rows(service.get("historical_evidence", [])):
            evidence(service.get("service", ""), "breach", "historical_breach",
                     historical.get("source", ""), historical.get("evidence", ""),
                     historical.get("url", ""), service.get("domain", ""))
        if service.get("registration_status") == "found":
            evidence(service.get("service", ""), "registration", "registration_signal",
                     service.get("registration_source", ""), service.get("registration_evidence", ""))

    # Legacy linked-services rows select one primary kind. Reconstruct retained
    # historical evidence so a public profile never hides a breach association.
    for provider, records in (("LeakCheck", (data.get("breaches") or {}).get("sources", [])),
                              ("XposedOrNot analytics", (data.get("darkweb") or {}).get("breaches", [])),
                              ("XposedOrNot fallback", (data.get("fallback") or {}).get("sources", [])),
                              ("LeakCheck Pro", (data.get("breach_details") or {}).get("records", []))):
        for record in _rows(records):
            name = _text(record.get("name"), 100)
            if not name or record.get("compilation") or _COMPILATION.search(name):
                continue
            evidence(name, "breach", "historical_breach", provider,
                     "Historical service exposure reported by " + provider, domain=record.get("domain", ""))

    registration = data.get("registration_checks") or {}
    for item in _rows(registration.get("services", [])):
        check(item.get("service", ""), item.get("status", "unknown"), "Holehe",
              item.get("domain", ""), item.get("reason", ""))
        if item.get("status") == "found":
            evidence(item.get("service", ""), "registration", "registration_signal",
                     "Holehe", item.get("reason", ""), domain=item.get("domain", ""))
    for item in _rows(report.get("registrations", [])) + _rows(enrichment.get("registrations", [])):
        if item.get("status") != "found":
            continue
        check(item.get("service", ""), "found", item.get("source", "Registration provider"), item.get("domain", ""))
        evidence(item.get("service", ""), "registration", "registration_signal",
                 item.get("source", ""), item.get("reason", ""), domain=item.get("domain", ""))

    def source(item, scope):
        name, state = _text(item.get("name"), 100), _text(item.get("status"), 40)
        if not name:
            return
        projected = {"name": name, "provider": _text(item.get("provider"), 100),
                     "status": state or "unknown", "scope": scope}
        if projected not in source_rows:
            source_rows.append(projected)
        if scope == "profiles" and canonical_platform(name)[0] in _ALIASES:
            check(name, state, name, provider=projected["provider"])

    for item in _rows(account_checks.get("sources", [])):
        if item.get("name") != "Profile enrichment" or not enrichment.get("sources"):
            source(item, "profiles")
    for item in _rows(enrichment.get("sources", [])):
        # Review retrieval has its own coverage and cannot establish accounts.
        source(item, "reviews" if "review" in _text(item.get("name")).lower() else "profiles")
    if enabled and registration.get("status"):
        source({"name": "Holehe", "status": registration["status"]}, "registrations")

    counts = {key: 0 for key in ("total_platforms", "linked_platforms", "public_profile_platforms",
                               "registration_platforms", "historical_platforms",
                               "historical_only_platforms", "owner_declared_platforms")}
    coverage = {key: 0 for key in ("checked", "attempted", "found", "not_found", "unknown", "skipped")}
    for row in rows.values():
        bases = set(row["basis"])
        row["linked"] = bool(bases & _LINKED)
        row["historical"] = bool(bases & _HISTORICAL)
        row["owner_declared"] = bool(bases & _DECLARED)
        row["historical_only"] = row["historical"] and not row["linked"]
        states = checks.get(row["id"], set())
        # A negative answer from one source cannot settle an incomplete check.
        state = "found" if "found" in states else "unknown" if "unknown" in states else "not_found" if "not_found" in states else "skipped"
        row["status"] = "found" if row["evidence"] else state
        row["check_status"] = state
        if states:
            coverage[state] += 1
        counts["total_platforms"] += bool(row["evidence"])
        counts["linked_platforms"] += row["linked"]
        counts["public_profile_platforms"] += "profile" in row["kinds"]
        counts["registration_platforms"] += "registration_signal" in bases
        counts["historical_platforms"] += row["historical"]
        counts["historical_only_platforms"] += row["historical_only"]
        counts["owner_declared_platforms"] += row["owner_declared"]
    coverage["checked"] = coverage["found"] + coverage["not_found"]
    coverage["attempted"] = coverage["checked"] + coverage["unknown"]
    coverage.update(catalogue_platforms=len(checks), source_count=len(source_rows), sources=source_rows)
    incomplete = coverage["unknown"] > 0 or any(
        item["scope"] != "reviews" and item["status"] not in _SKIPPED | {"ok", "found", "not_found", "no_match"}
        for item in source_rows)
    status = "skipped" if not enabled else "partial" if incomplete and (coverage["checked"] or counts["linked_platforms"]) else "unavailable" if incomplete else "ok"
    return {"version": 1, "enabled": enabled, "status": status, "counts": counts,
            "platforms": sorted(rows.values(), key=lambda row: (not bool(row["evidence"]), row["name"].casefold())),
            "coverage": coverage,
            "note": "Distinct platforms with returned evidence; categories overlap. Linked means a source-associated profile or positive registration signal, not verified active ownership. Historical and owner-declared-only associations are counted separately. A missing match or no registration signal does not prove no account."}
