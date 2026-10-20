"""Server-side guest projections and short-lived, authenticated report reveal.

Only the explicit card/section projections below may cross the guest response
boundary. The original JSON stays in this single-worker process for at most
30 minutes, never in browser storage or the shared result cache under a token.
Retention is bounded by both report count and serialized bytes. A restart or
capacity eviction returns an honest expired response, never an automatic scan.
"""

import json
import re
import secrets
import threading
import time
from collections import OrderedDict
from copy import deepcopy

TTL_SECONDS = 30 * 60
MAX_REPORTS = 64
MAX_BYTES = 24 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_reports = OrderedDict()
_lock = threading.RLock()
_expiry_changed = threading.Condition(_lock)
_cleanup_started = False
_bytes = 0
_STATES = {"ok", "partial", "pending", "found", "no_match", "not_found", "error",
           "disabled", "unconfigured", "authentication_required", "rate_limited",
           "timeout", "unavailable", "unknown", "skipped", "credits_exhausted"}


def _state(value, default="unavailable"):
    return value if isinstance(value, str) and value in _STATES else default


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _remove(token):
    global _bytes
    row = _reports.pop(token, None)
    if row:
        _bytes -= row["bytes"]


def _prune(now):
    for token, row in list(_reports.items()):
        if row["expires_at"] <= now:
            _remove(token)


def _cleanup():
    """Remove expired payloads even when no further requests reach the server."""
    global _cleanup_started
    with _expiry_changed:
        while _reports:
            now = time.time()
            _prune(now)
            if _reports:
                next_expiry = min(row["expires_at"] for row in _reports.values())
                _expiry_changed.wait(timeout=max(0.1, next_expiry - now))
        _cleanup_started = False


def retain(tool, data, *, token=None, complete=True):
    """Retain a JSON snapshot and return public receipt metadata only.

    The token is random, independent of query/IP/cache key, and is not enough
    to reveal a report without verified Firebase authentication.
    """
    global _bytes, _cleanup_started
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    size = len(encoded.encode("utf-8"))
    now = time.time()
    with _lock:
        _prune(now)
        existing = _reports.get(token) if token else None
        if token and existing is None:
            # A later streaming snapshot cannot resurrect an expired/evicted
            # token or forget the owner to whom its report was already bound.
            return {"report_token": None, "expires_at": None, "complete": bool(complete),
                    "retention_unavailable": True}
        expires = existing["expires_at"] if existing else int(now) + TTL_SECONDS
        # Oversized reports still get a safe guest projection, with an explicit
        # unavailable receipt instead of risking the backend's memory budget.
        if size > MAX_REPORT_BYTES:
            if token:
                _remove(token)
            return {"report_token": None, "expires_at": None, "complete": complete,
                    "retention_unavailable": True}
        token = token or secrets.token_urlsafe(32)
        owner = existing.get("uid") if existing else None
        if existing:
            _remove(token)
        while _reports and (len(_reports) >= MAX_REPORTS or _bytes + size > MAX_BYTES):
            _remove(next(iter(_reports)))
        _reports[token] = {"tool": tool, "payload": encoded, "bytes": size,
                           "expires_at": expires, "complete": bool(complete), "uid": owner}
        _bytes += size
        if not _cleanup_started:
            _cleanup_started = True
            try:
                threading.Thread(target=_cleanup, name="guest-report-expiry", daemon=True).start()
            except Exception:
                _cleanup_started = False
                _remove(token)
                return {"report_token": None, "expires_at": None, "complete": bool(complete),
                        "retention_unavailable": True}
        _expiry_changed.notify_all()
        return {"report_token": token, "expires_at": expires, "complete": bool(complete)}


def read(token, uid=None):
    """Read a private receipt, optionally binding it to its first signed-in owner.

    Calling without uid is server-internal metadata inspection. No public
    endpoint returns this data until it has authenticated and checked plans.
    """
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        return None
    with _lock:
        _prune(time.time())
        row = _reports.get(token)
        if not row or (row["uid"] and uid and row["uid"] != uid):
            return None
        if uid:
            row["uid"] = uid
        return {"tool": row["tool"], "data": json.loads(row["payload"]),
                "complete": row["complete"], "expires_at": row["expires_at"]}


def failed(token):
    row = read(token)
    if row:
        data = {**row["data"], "status": "error", "partial": True}
        retain(row["tool"], data, token=token, complete=False)


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


def deep(data, *, token=None, complete=False):
    data = data if isinstance(data, dict) else {"status": "error"}
    return {"status": _state(data.get("status", "pending")),
            "subject": data.get("subject", ""), "mode": data.get("mode", "handle"),
            "context": data.get("context"), "partial": bool(data.get("partial")),
            "guest_access": {**retain("deep_search", data, token=token, complete=complete),
                             "locked": True, "sections": deep_sections(data)}}


def progress(event, *, deep_search=False):
    """Never reflect site names, verdicts, queries, provider errors or snippets."""
    percent = event.get("percent", 0)
    percent = max(0, min(100, percent)) if isinstance(percent, (int, float)) else 0
    queued = event.get("phase") == "Queued"
    return {"type": "progress", "percent": percent,
            "phase": "Queued" if queued else "Investigating" if deep_search else "Scanning",
            "detail": "Waiting for a scan slot." if queued else
            "Checking public sources. Finding details appear after sign-in." if deep_search else
            "Checking platforms and preparing result cards."}
