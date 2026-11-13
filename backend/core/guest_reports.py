"""Guest response projections. No server report retention or reveal receipts."""

import re
from copy import deepcopy

_STATES = {"ok", "partial", "pending", "found", "no_match", "not_found", "error",
           "disabled", "unconfigured", "authentication_required", "rate_limited",
           "timeout", "unavailable", "unknown", "skipped", "credits_exhausted"}


def _state(value, default="unavailable"):
    return value if isinstance(value, str) and value in _STATES else default


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def retain(tool, data, *, token=None, complete=True):
    return {"report_token": None, "expires_at": None, "complete": bool(complete),
            "retention_unavailable": True}


def read(token, uid=None):
    return None


def failed(token):
    pass


def _card(kind, title, data):
    return {"kind": kind, "title": title, "data": data}


def _breach_cards(data):
    """Mirror the website's named-breach deduplication and date ordering."""
    rows = {}

    def key(name):
        name = re.sub(r"\.(com|net|org|io|co|me|ru|de|fr|uk|in)$", "", str(name or "").lower())
        return re.sub(r"[^a-z0-9]", "", name)

    def add(record, source, detailed):
        name = record.get("name")
        ident = key(name)
        if not ident:
            return
        existing = rows.get(ident)
        if existing:
            if source not in existing["sources"]:
                existing["sources"].append(source)
            date, previous = str(record.get("date") or ""), str(existing.get("date") or "")
            if date and (not previous or (date.startswith(previous + "-")
                                         and re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", date))):
                existing["date"] = date
        else:
            rows[ident] = {**deepcopy(record), "detailed": detailed, "sources": [source]}

    for breach in _rows((data.get("darkweb") or {}).get("breaches")):
        add(breach, "XposedOrNot analytics", True)
    for field, fallback in (("breaches", "LeakCheck"), ("fallback", "XposedOrNot fallback")):
        source = data.get(field) or {}
        if source.get("status") != "skipped":
            for breach in _rows(source.get("sources")):
                add(breach, source.get("source") or fallback, False)
    for record in _rows((data.get("breach_details") or {}).get("records")):
        add(record, "LeakCheck Pro", True)
        ident = key(record.get("name"))
        if ident in rows:
            rows[ident].setdefault("identities", []).append(deepcopy(record))
    ordered = sorted(rows.values(), key=lambda r: str(r.get("name") or "").lower())
    ordered.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
    return [_card("breach", str(row.get("name") or "Breach"), row) for row in ordered]


def standard_cards(tool, data):
    """Actual finding cards, excluding progress, notices and aggregate summaries."""
    cards = []
    if tool in ("username", "fullname", "image"):
        results = data.get("results") or {}
        rows = results if isinstance(results, list) else [
            row for category in ("profiles", "documents", "mentions")
            for row in _rows(results.get(category))]
        return [_card("profile", "Public result", row) for row in _rows(rows)]
    if tool == "email":
        cards.extend(_breach_cards(data))
        evidence = data.get("evidence_report") or {}
        profiles = _rows(evidence.get("profiles"))
        if profiles:
            for row in profiles:
                collections = {key: _rows(row.get(key)) for key in ("reviews", "positions", "education")}
                # A profile card can contain multiple further article cards.
                # Their finding details must consume their own preview slots,
                # never travel inside a visible owner-profile payload.
                profile_keys = ("platform", "username", "display_name", "url", "avatar_url", "bio",
                                "location", "company", "fields", "stats", "lists", "website",
                                "evidence", "evidence_url", "basis", "source", "profile_status",
                                "last_seen", "confidence", "freshness", "review_source", "review_coverage")
                profile = {key: deepcopy(row[key]) for key in profile_keys if key in row}
                profile["_guest_collections_locked"] = any(collections.values())
                conflicts = row.get("field_conflicts") or {}
                if isinstance(conflicts, dict):
                    profile["field_conflicts"] = {key: deepcopy(values) for key, values in conflicts.items()
                                                  if isinstance(key, str)
                                                  and key.split(".")[0] in profile_keys
                                                  and key.split(".")[0] not in ("review_coverage", "review_source")}
                # Review coverage can include venue/source attributes. Keep
                # only availability/count metadata belonging to this card.
                if isinstance(profile.get("review_coverage"), dict):
                    profile["review_coverage"] = {key: profile["review_coverage"][key]
                                                  for key in ("status", "returned", "total_reported", "limited", "limit")
                                                  if key in profile["review_coverage"]}
                cards.append(_card("email_profile", str(row.get("platform") or "Public profile"), profile))
                for review in collections["reviews"]:
                    shown = {key: deepcopy(review[key]) for key in
                             ("id", "name", "address", "text", "rating", "date", "date_label", "owner_reply",
                              "owner_reply_date", "latitude", "longitude", "maps_url", "source_url", "source", "confidence")
                             if key in review}
                    cards.append(_card("email_review", "Google review", shown))
                for position in collections["positions"]:
                    shown = {key: deepcopy(position[key]) for key in
                             ("title", "company", "start", "end", "current", "description", "url", "source")
                             if key in position}
                    cards.append(_card("email_position", "LinkedIn position", shown))
                for education in collections["education"]:
                    shown = {key: deepcopy(education[key]) for key in
                             ("school", "degree", "start", "end", "current", "field_of_study", "description", "url", "source")
                             if key in education}
                    cards.append(_card("email_education", "LinkedIn education", shown))
        # Registration and other evidence entries are finding cards as well.
        # Historical breach/profile entries already represented above are not
        # repeated and cannot consume another visible slot.
        represented_profiles = {str(row.get("platform") or "").lower() for row in profiles}
        if not evidence:
            if (data.get("gravatar") or {}).get("exists"):
                represented_profiles.add("gravatar")
            if data.get("github"):
                represented_profiles.add("github")
        for row in _rows((data.get("linked_services") or {}).get("services")):
            if row.get("kind") != "breach" and str(row.get("service") or "").lower() not in represented_profiles:
                cards.append(_card("service", str(row.get("service") or "Service evidence"), row))
        if not evidence:
            gravatar, github = data.get("gravatar") or {}, data.get("github") or {}
            if gravatar.get("exists"):
                # Declared accounts become their own service cards above;
                # they must not leak through the visible Gravatar payload.
                shown = {key: gravatar[key] for key in ("exists", "display_name", "profile_url", "bio", "avatar_url")
                         if key in gravatar}
                cards.append(_card("gravatar", "Gravatar profile", shown))
            if github:
                shown = {key: github[key] for key in ("username", "url", "evidence", "avatar_url", "evidence_url")
                         if key in github}
                cards.append(_card("github", "GitHub", shown))
        return cards
    if tool in ("domain", "dns", "whois", "ip"):
        if tool in ("domain", "whois"):
            whois = (data.get("whois") or {}) if tool == "domain" else data
            if whois.get("found"):
                cards.append(_card("whois", "Registration (WHOIS / RDAP)", whois))
        if tool in ("domain", "dns"):
            dns = (data.get("dns") or {}) if tool == "domain" else data
            ms = dns.get("mail_security") or {}
            if ms.get("verdict") in ("protected", "partial", "exposed"):
                cards.append(_card("mail_security", "Email spoofing protection", ms))
            if any(_rows(rows) for rows in (dns.get("records") or {}).values()):
                cards.append(_card("dns", "DNS records", {"records": dns["records"], "summary": dns.get("summary") or {}}))
        if tool in ("domain", "ip"):
            ip = (data.get("primary_ip") or {}) if tool == "domain" else data
            if ip.get("found"):
                cards.append(_card("ip", "IP intelligence", ip))
        return cards
    return cards


def standard(tool, data, *, token=None, complete=True):
    data = data if isinstance(data, dict) else {"status": "error"}
    cards = standard_cards(tool, data)
    count = len(cards)
    # Discard ALL fields outside the projection, including timelines, clusters,
    # avatar URLs, platform-check logs, breach metadata, provider errors and
    # accessibility/export strings that could identify a hidden finding.
    coverage = data.get("coverage") or {}
    partial = bool(data.get("partial") or data.get("errors") or coverage.get("unchecked")
                   or coverage.get("unreachable") or coverage.get("undetermined"))
    status = _state(data.get("status", "ok"))
    if tool == "email":
        outcome = (data.get("summary") or {}).get("breach_outcome")
        partial = partial or bool(outcome and outcome not in ("found", "no_match"))
    elif tool in ("ip", "whois"):
        partial = partial or bool(not data.get("found") and data.get("error"))
    elif tool == "domain":
        partial = partial or any(not source.get("found") and source.get("error")
                                 for source in (data.get("whois") or {}, data.get("primary_ip") or {}))
    query = {key: value for key, value in (data.get("query") or {}).items()
             if key in ("username", "full_name", "email", "domain", "ip", "image_url", "deep", "scope")
             and isinstance(value, (str, bool))}
    notices = []
    if status == "error":
        notices.append("The lookup could not complete. Please try again.")
    elif partial:
        notices.append("Some sources could not be checked. The cards show findings returned by completed sources.")
    if not count and status != "error":
        notices.append("No result cards were returned by the available sources. This does not prove there are no records.")
    if data.get("notice"):
        notices.append("This lookup has a source configuration or availability limitation.")
    access = {**retain(tool, data, token=token, complete=complete), "locked": count > 2,
              "total_cards": count, "visible_cards": min(2, count), "locked_count": max(0, count - 2)}
    return {"status": status, "query": query, "partial": partial, "notices": notices,
            "guest_access": access,
            "cards": [deepcopy(card) if index < 2 else {"locked": True}
                      for index, card in enumerate(cards)]}


def deep_sections(data):
    """Visible headings from real returned groups, with no finding attributes."""
    from modules.deep_search_plan import LABELS
    sections = []
    google = data.get("google_public_profiles")
    if isinstance(google, dict):
        profiles = _rows(google.get("profiles"))
        sections.append({"label": "Public Profiles", "count": len(profiles),
                         "status": _state(google.get("status", "pending"))})
        review_count = sum(len(_rows(profile.get("reviews"))) for profile in profiles)
        review_sources = [source for source in _rows(google.get("sources"))
                          if source.get("name") == "Google Maps public reviews"]
        coverage = [(profile.get("review_coverage") or {}).get("status") for profile in profiles]
        coverage.extend(source.get("status") for source in review_sources)
        # Google Reviews is a real attempted section even if the source was
        # private/unavailable or returned an empty collection. Keep that state.
        if profiles or review_sources:
            state = next((s for s in coverage if s not in ("ok", "no_match", "not_found")),
                         "ok" if review_count else "no_match")
            sections.append({"label": "Google Reviews", "count": review_count, "status": _state(state)})
    for key, label in (("people", "Public figure records"), ("accounts", "Name matches"),
                       ("activity", "Public accounts & recent activity"),
                       ("owner_links", "Links declared by account owners"),
                       ("connections", "Explore linked profiles")):
        rows = _rows(data.get(key))
        if rows:
            sections.append({"label": label, "count": len(rows), "status": "found"})
    trail = _rows(data.get("connection_trail"))
    if trail:
        sections.append({"label": "Connection trail", "count": len(trail), "status": "found"})
    proofs = _rows((data.get("identity") or {}).get("proofs"))
    if proofs:
        sections.append({"label": "Keybase published proofs", "count": len(proofs), "status": "found"})
    for section in _rows(data.get("sections")):
        hits = _rows(section.get("hits"))
        label = LABELS.get(section.get("section"))
        if hits and label:
            sections.append({"label": label, "count": len(hits), "status": "found"})
    return sections


def _deep_preview(data):
    """One actual finding; never send nested collections of locked findings."""
    profiles = _rows((data.get("google_public_profiles") or {}).get("profiles"))
    if profiles:
        cards = standard_cards("email", {"evidence_report": {"profiles": profiles}})
        card = next((row for row in cards if row["kind"] == "email_review"), None)
        card = card or next((row for row in cards if row["kind"] == "email_profile"), None)
        if card:
            return {**card, "section": "Google Reviews" if card["kind"] == "email_review" else "Public Profiles"}
    for key, label in (("activity", "Public accounts & recent activity"),
                       ("accounts", "Name matches"), ("people", "Public figure records")):
        rows = _rows(data.get(key))
        if rows:
            row = rows[0]
            shown = {key: deepcopy(row[key]) for key in
                     ("platform", "handle", "name", "display_name", "url", "bio", "description", "detail", "source")
                     if key in row}
            return {"kind": "public_result", "title": "Public profile", "section": label, "data": shown}
    from modules.deep_search_plan import LABELS
    for section in _rows(data.get("sections")):
        rows = _rows(section.get("hits"))
        if rows and section.get("section") in LABELS:
            row = rows[0]
            return {"kind": "public_result", "title": "Indexed public result",
                    "section": LABELS[section["section"]], "data": {
                        key: deepcopy(row[key]) for key in ("title", "url", "snippet", "source") if key in row}}
    for key, label in (("owner_links", "Links declared by account owners"),
                       ("connections", "Explore linked profiles")):
        rows = _rows(data.get(key))
        if rows:
            row = rows[0]
            if key == "connections":
                row = row.get("destination") or {}
            return {"kind": "public_result", "title": "Public profile link", "section": label,
                    "data": {key: deepcopy(row[key]) for key in ("url", "label", "handle", "platform", "source") if key in row}}
    proofs = _rows((data.get("identity") or {}).get("proofs"))
    if proofs:
        row = proofs[0]
        return {"kind": "public_result", "title": "Keybase published proof", "section": "Keybase published proofs",
                "data": {key: deepcopy(row[key]) for key in ("url", "platform", "handle") if key in row}}
    return None


def deep(data, *, token=None, complete=False):
    data = data if isinstance(data, dict) else {"status": "error"}
    sections = deep_sections(data)
    # Reveal only on completion so successive partial snapshots cannot expose
    # a different free finding each time a faster source returns.
    preview = _deep_preview(data) if complete else None
    total = sum(section["count"] for section in sections)
    return {"status": _state(data.get("status", "pending")),
            "subject": data.get("subject", ""), "mode": data.get("mode", "handle"),
            "context": data.get("context"), "partial": bool(data.get("partial")),
            "guest_access": {**retain("deep_search", data, token=token, complete=complete),
                             "locked": True, "sections": sections, "preview": preview,
                             "visible_count": int(preview is not None),
                             "locked_count": max(0, total - int(preview is not None))}}


def progress(event, *, deep_search=False):
    """Never reflect site names, verdicts, queries, provider errors or snippets."""
    percent = event.get("percent", 0)
    percent = max(0, min(100, percent)) if isinstance(percent, (int, float)) else 0
    queued = event.get("phase") == "Queued"
    return {"type": "progress", "percent": percent,
            "phase": "Queued" if queued else "Investigating" if deep_search else "Scanning",
            "detail": "Waiting for a scan slot." if queued else
            "Checking public sources. One returned finding will be shown as a free preview." if deep_search else
            "Checking platforms and preparing result cards."}
