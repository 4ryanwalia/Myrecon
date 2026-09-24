"""
Renderers: one function per command, each turning a service result into text.

These are deliberately tolerant readers. Every field is fetched with `.get()`
and skipped when empty, so a backend that grows a key does not break the CLI
and one that drops a key prints a shorter report instead of a traceback. The
`--json` flag exists for anything this layer chooses not to show.

House rule carried over from the web UI: never state more than the evidence
supports. Accounts that merely share a handle are labelled as exactly that.
"""

from __future__ import annotations

from cli import ui


def _truncate(text, limit: int = 70) -> str:
    text = str(text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _num(value):
    """Thousand-separate counts. A leak of 7252200506 records is unreadable."""
    return "{:,}".format(value) if isinstance(value, int) else value


def _confidence_style(score) -> str:
    try:
        score = int(score)
    except (TypeError, ValueError):
        return "grey"
    if score >= 70:
        return "green"
    if score >= 40:
        return "yellow"
    return "grey"


# ── Username / full name ─────────────────────────────────────────

def username_report(data: dict, show_all: bool = False) -> None:
    query = data.get("query") or {}
    ui.heading("Username scan", str(query.get("username", "")) +
               ("  (deep)" if query.get("deep") else ""))
    _findings(data, show_all)


def fullname_report(data: dict, show_all: bool = False) -> None:
    query = data.get("query") or {}
    ui.heading("Full-name search", str(query.get("full_name", "")) +
               ("  (deep)" if query.get("deep") else ""))
    _findings(data, show_all)


def _findings(data: dict, show_all: bool = False) -> None:
    """The body both search reports share: counts, then each result bucket."""
    summary = data.get("summary") or {}
    results = data.get("results") or {}

    ui.count_line("confirmed profiles", summary.get("profiles", 0), "green")
    ui.count_line("documents", summary.get("documents", 0))
    ui.count_line("mentions", summary.get("mentions", 0))
    if summary.get("checked"):
        ui.count_line("platforms checked", summary.get("checked", 0), "grey")
    if summary.get("exposures"):
        ui.count_line("exposures", summary.get("exposures", 0), "yellow")

    profiles = results.get("profiles") or []
    if profiles:
        ui.section("Profiles")
        rows = []
        for p in profiles:
            marker = ui.glyph("tick") if p.get("confidence") == "high" else ui.glyph("dot")
            detail = p.get("display_name") or p.get("title") or ""
            followers = p.get("followers")
            if followers:
                detail = ((detail + "  " if detail else "") +
                          str(_num(followers)) + " followers")
            rows.append([marker, p.get("platform", ""), _truncate(detail, 34),
                         p.get("url", "")])
        ui.table(["", "platform", "detail", "url"], rows)

    documents = results.get("documents") or []
    if documents:
        ui.section("Documents")
        for d in documents[: None if show_all else 10]:
            ui.bullet(_truncate(d.get("title") or d.get("url"), 66))
            ui.line(str(d.get("url", "")), indent=4, style="grey")
        if not show_all and len(documents) > 10:
            ui.line("+ " + str(len(documents) - 10) + " more (--all)", indent=4, style="grey")

    mentions = results.get("mentions") or []
    if mentions:
        ui.section("Mentions")
        ui.line("Unconfirmed — the handle appears here, the account is not verified.",
                indent=2, style="grey")
        for m in mentions[: None if show_all else 10]:
            ui.bullet(_truncate((m.get("platform") or "") + "  " +
                                (m.get("title") or m.get("url") or ""), 66))
        if not show_all and len(mentions) > 10:
            ui.line("+ " + str(len(mentions) - 10) + " more (--all)", indent=4, style="grey")

    for exposure in data.get("exposures") or []:
        ui.section("Exposure")
        if exposure.get("type") == "commit_email":
            emails = exposure.get("emails") or []
            if emails:
                ui.line("Public commit metadata on GitHub exposes:", indent=2)
                for item in emails:
                    address = item.get("email") if isinstance(item, dict) else item
                    ui.bullet(str(address), indent=4, style="yellow")
            if exposure.get("protected"):
                ui.line("Commit email is protected by GitHub.", indent=2, style="green")
            if exposure.get("error"):
                ui.line(str(exposure["error"]), indent=2, style="grey")
        else:
            ui.kv(str(exposure.get("type", "finding")), _truncate(exposure, 60))

    clusters = data.get("identity_clusters") or []
    if clusters:
        ui.section("Identity clusters")
        for c in clusters[:5]:
            score = c.get("confidence", 0)
            names = c.get("platform_names") or []
            shown = ", ".join(names[:6])
            if len(names) > 6:
                shown += " +" + str(len(names) - 6) + " more"
            ui.line(ui.paint(str(score).rjust(3) + "/100", _confidence_style(score)) +
                    "  " + str(c.get("username", "")) + "  " +
                    ui.paint(shown, "grey"))
            if c.get("display_name") or c.get("bio"):
                ui.line(_truncate(c.get("display_name") or c.get("bio"), 70),
                        indent=6, style="grey")
        ui.line("Accounts sharing a handle are often unrelated people.",
                indent=2, style="grey")

    rejected = data.get("rejected") or []
    if rejected and show_all:
        ui.section("Checked and not reported")
        ui.table(["platform", "code", "reason"],
                 [[r.get("platform", ""), r.get("status_code", ""),
                   _truncate(r.get("reason"), 48)] for r in rejected])
    elif rejected:
        ui.line("")
        ui.line(str(len(rejected)) + " platforms were checked and not reported "
                "(--all to list them).", indent=2, style="grey")

    if data.get("notice"):
        ui.line("")
        ui.line(str(data["notice"]), indent=2, style="yellow")


# ── Email ────────────────────────────────────────────────────────

def email_report(data: dict) -> None:
    query = data.get("query") or {}
    summary = data.get("summary") or {}
    analysis = data.get("analysis") or {}

    ui.heading("Email intelligence", str(query.get("email", "")))

    breached = summary.get("breached")
    ui.line(
        ui.paint(ui.glyph("cross") + " Found in known breaches", "red")
        if breached else
        ui.paint(ui.glyph("tick") + " Not found in the breach sources checked", "green")
    )
    if summary.get("risk_label"):
        ui.kv("risk", str(summary.get("risk_label")) + "  " +
              str(summary.get("risk_score", "")) + "/100")
    ui.kv("breaches", _num(summary.get("breach_count")))
    ui.kv("leaked records", _num(summary.get("records_found")))
    ui.kv("records exposed", _num(summary.get("records_exposed")))
    ui.kv("linked accounts", summary.get("linked_accounts"))

    if analysis:
        ui.section("Address")
        for key in ("local_part", "domain", "provider", "provider_type",
                    "format", "plus_addressing", "disposable", "has_mx",
                    "deliverable"):
            ui.kv(key.replace("_", " "), analysis.get(key), indent=4)
        ui.kv("mx hosts", _truncate(", ".join(analysis.get("mx_hosts") or []), 60),
              indent=4)

    gravatar = data.get("gravatar") or {}
    if gravatar.get("exists"):
        ui.section("Gravatar")
        ui.kv("profile", gravatar.get("profile_url"), indent=4)
        ui.kv("display name", gravatar.get("display_name"), indent=4)
        ui.kv("bio", _truncate(gravatar.get("bio"), 60), indent=4)
        ui.kv("avatar", gravatar.get("avatar_url"), indent=4)
        for account in gravatar.get("accounts") or []:
            ui.bullet(str(account.get("name", "")) + "  " + str(account.get("url", "")),
                      indent=6)

    github = data.get("github") or {}
    if github:
        ui.section("GitHub")
        ui.kv("user", github.get("username"), indent=4)
        ui.kv("profile", github.get("url"), indent=4)

    for label, block in (("Breach sources", data.get("breaches")),
                         ("Dark-web records", data.get("darkweb")),
                         ("Have I Been Pwned", data.get("hibp"))):
        if not isinstance(block, dict) or not block:
            continue
        sources = block.get("sources") or block.get("breaches") or []
        if not sources and not block.get("breached"):
            continue
        ui.section(label)
        ui.kv("count", _num(block.get("count")), indent=4)
        if block.get("risk_label"):
            ui.kv("risk", block.get("risk_label"), indent=4)
        if block.get("exposed_data"):
            ui.kv("data types", _truncate(", ".join(str(x) for x in
                                                    block["exposed_data"]), 60), indent=4)
        rows = []
        for source in sources[:25]:
            if not isinstance(source, dict):
                continue
            exposed = source.get("exposed") or source.get("fields") or []
            if isinstance(exposed, list):
                exposed = ", ".join(str(x) for x in exposed)
            rows.append([_truncate(source.get("name"), 30),
                         source.get("date") or source.get("breach_date") or "",
                         _num(source.get("records")) or "",
                         _truncate(exposed or source.get("details"), 36)])
        ui.table(["source", "date", "records", "exposed"], rows, indent=4)
        if len(sources) > 25:
            ui.line("+ " + str(len(sources) - 25) + " more (--json for all)",
                    indent=4, style="grey")


# ── Network ──────────────────────────────────────────────────────

_MAIL_VERDICT = {
    "protected": ("protected against spoofing", "green"),
    "partial": ("partly protected", "yellow"),
    "exposed": ("open to spoofing", "red"),
}


def _mail_security(ms: dict) -> None:
    """SPF + DMARC verdict, the same grading the website shows."""
    if not ms or ms.get("verdict") not in _MAIL_VERDICT:
        return
    label, style = _MAIL_VERDICT[ms["verdict"]]
    spf = ms.get("spf") or {}
    dmarc = ms.get("dmarc") or {}
    ui.section("Email spoofing")
    ui.line(ui.paint(label, style), indent=4)
    ui.kv("spf", (spf.get("all") or "published") if spf.get("present") else "not published", indent=4)
    ui.kv("dmarc", ("p=" + str(dmarc.get("policy"))) if dmarc.get("present") else "not published", indent=4)
    for issue in ms.get("issues") or []:
        ui.bullet(issue, indent=4, style="grey")


def dns_report(data: dict) -> None:
    query = data.get("query") or {}
    ui.heading("DNS records", str(query.get("domain", "")))
    _mail_security(data.get("mail_security"))
    records = data.get("records") or {}
    if not records:
        ui.line("No records returned.", indent=2, style="grey")
        return
    for rtype, entries in records.items():
        ui.section(rtype)
        for entry in entries:
            value = entry.get("value") if isinstance(entry, dict) else entry
            ttl = entry.get("ttl") if isinstance(entry, dict) else None
            ui.bullet(_truncate(value, 72) + (ui.paint("   ttl " + str(ttl), "grey")
                                              if ttl else ""), indent=4)


def whois_report(data: dict) -> None:
    query = data.get("query") or {}
    ui.heading("Registration (RDAP/WHOIS)", str(query.get("domain", "")))
    if not data.get("found"):
        ui.line("No registration record found.", indent=2, style="grey")
        return
    ui.kv("registrar", data.get("registrar"))
    ui.kv("created", data.get("created"))
    ui.kv("updated", data.get("updated"))
    ui.kv("expires", data.get("expires"))
    ui.kv("dnssec", data.get("dnssec"))
    ui.kv("nameservers", data.get("nameservers"))
    ui.kv("statuses", data.get("statuses"))
    contacts = data.get("contacts") or {}
    for role, name in contacts.items():
        ui.kv(role, name)


def ip_report(data: dict) -> None:
    query = data.get("query") or {}
    ui.heading("IP address", str(query.get("ip", "")))
    if not data.get("found"):
        ui.line("No geolocation data returned.", indent=2, style="grey")
    geo = data.get("geo") or {}
    network = data.get("network") or {}
    flags = data.get("flags") or {}

    ui.kv("reverse dns", data.get("reverse_dns"))
    ui.kv("country", " ".join(x for x in [geo.get("country"),
                                          geo.get("country_code")] if x))
    ui.kv("region", geo.get("region"))
    ui.kv("city", " ".join(x for x in [geo.get("city"), geo.get("zip")] if x))
    ui.kv("continent", geo.get("continent"))
    ui.kv("timezone", geo.get("timezone"))
    if geo.get("latitude") is not None:
        ui.kv("coordinates", str(geo.get("latitude")) + ", " + str(geo.get("longitude")))
        ui.line("Place it:  myrecon geo " + str(geo.get("latitude")) + " " +
                str(geo.get("longitude")), indent=4, style="grey")
    ui.kv("isp", network.get("isp"))
    ui.kv("organisation", network.get("organization"))
    ui.kv("asn", network.get("asn") or network.get("as_name"))

    raised = [name for name, value in flags.items() if value]
    if raised:
        ui.section("Flags")
        for flag in raised:
            ui.bullet(flag, indent=4, style="yellow")


def subdomains_report(data: dict, show_all: bool = False) -> None:
    query = data.get("query") or {}
    ui.heading("Subdomains", str(query.get("domain", "")))
    subs = data.get("subdomains") or []
    ui.kv("source", data.get("source"))
    ui.kv("found", data.get("total", len(subs)))
    if data.get("truncated"):
        ui.kv("shown", len(subs))
    ui.line("")
    for sub in subs[: None if show_all else 40]:
        ui.bullet(str(sub), indent=4)
    if not show_all and len(subs) > 40:
        ui.line("+ " + str(len(subs) - 40) + " more (--all)", indent=4, style="grey")


def domain_report(data: dict) -> None:
    query = data.get("query") or {}
    ui.heading("Domain intelligence", str(query.get("domain", "")))

    whois = data.get("whois") or {}
    if whois.get("found"):
        ui.section("Registration")
        ui.kv("registrar", whois.get("registrar"), indent=4)
        ui.kv("created", whois.get("created"), indent=4)
        ui.kv("expires", whois.get("expires"), indent=4)
        ui.kv("nameservers", whois.get("nameservers"), indent=4)

    dns = data.get("dns") or {}
    records = dns.get("records") or {}
    if records:
        ui.section("DNS")
        for rtype, entries in records.items():
            values = [e.get("value") if isinstance(e, dict) else e for e in entries]
            ui.kv(rtype, _truncate(", ".join(str(v) for v in values), 66), indent=4)
    _mail_security(dns.get("mail_security"))

    primary = data.get("primary_ip") or {}
    if primary:
        geo = primary.get("geo") or {}
        network = primary.get("network") or {}
        ui.section("Primary IP")
        ui.kv("address", (primary.get("query") or {}).get("ip"), indent=4)
        ui.kv("reverse dns", primary.get("reverse_dns"), indent=4)
        ui.kv("country", geo.get("country"), indent=4)
        ui.kv("city", geo.get("city"), indent=4)
        ui.kv("isp", network.get("isp"), indent=4)
        ui.kv("asn", network.get("asn"), indent=4)

    resolved = data.get("resolved_ips") or []
    if resolved:
        ui.kv("resolved ips", ", ".join(str(ip) for ip in resolved), indent=2)


# ── Profiles, archive, images, places ────────────────────────────

def enrich_report(data: dict) -> None:
    profile = data.get("profile") or {}
    ui.heading("Profile", str(profile.get("platform", "")) + " / " +
               str(profile.get("username", "")))
    ui.kv("url", profile.get("url"))
    ui.kv("display name", profile.get("display_name"))
    ui.kv("bio", _truncate(profile.get("bio"), 70))
    ui.kv("followers", _num(profile.get("followers")))
    ui.kv("following", _num(profile.get("following")))
    ui.kv("posts", _num(profile.get("posts")))
    ui.kv("private", profile.get("is_private"))
    ui.kv("verified", profile.get("is_verified"))
    ui.kv("avatar", profile.get("profile_pic_url"))
    if profile.get("error"):
        ui.note(str(profile["error"]))


def wayback_report(data: dict, url: str) -> None:
    ui.heading("Archive history", url)
    if data.get("rate_limited"):
        ui.line("archive.org is throttling requests right now — try again shortly. "
                "This is not an answer about the URL.", indent=2, style="yellow")
        return
    if not data.get("snapshots"):
        ui.line("No captures found for this URL.", indent=2, style="grey")
        return
    ui.kv("first seen", data.get("first_seen"))
    ui.kv("last seen", data.get("last_seen"))
    ui.kv("captures", data.get("snapshots"))
    ui.kv("latest", data.get("archive_url"))


def image_report(data: dict, show_all: bool = False) -> None:
    query = data.get("query") or {}
    summary = data.get("summary") or {}
    ui.heading("Reverse image search", _truncate(query.get("image_url"), 60))
    ui.count_line("results", summary.get("total", 0))
    ui.count_line("profiles", summary.get("profiles", 0), "green")
    ui.count_line("mentions", summary.get("mentions", 0))

    results = data.get("results") or []
    if results:
        ui.section("Hits")
        for r in results[: None if show_all else 20]:
            ui.bullet(_truncate(r.get("title") or r.get("url"), 66))
            ui.line(str(r.get("url", "")), indent=4, style="grey")
        if not show_all and len(results) > 20:
            ui.line("+ " + str(len(results) - 20) + " more (--all)", indent=4, style="grey")


def forensics_report(data: dict) -> None:
    file_info = data.get("file") or {}
    ui.heading("Image forensics", str(file_info.get("filename") or ""),)
    ui.line("Computed from the file bytes. No network call, no third party.",
            indent=2, style="grey")

    ui.section("File")
    for key in ("format", "mime", "mode", "width", "height", "megapixels",
                "aspect_ratio", "animated", "size_bytes", "md5", "sha256"):
        ui.kv(key.replace("_", " "), file_info.get(key), indent=4)

    perceptual = data.get("perceptual") or {}
    if perceptual:
        ui.section("Perceptual hashes")
        for key in ("ahash", "dhash", "phash"):
            ui.kv(key, perceptual.get(key), indent=4)
        if perceptual.get("note"):
            ui.line(str(perceptual["note"]), indent=4, style="grey")

    exif = data.get("exif") or {}
    ui.section("EXIF")
    if not exif.get("present"):
        ui.line("No EXIF metadata — stripped on upload, or never written.",
                indent=4, style="grey")
    else:
        ui.kv("tags", exif.get("raw_tag_count"), indent=4)
        ui.kv("software", _truncate(exif.get("software"), 56), indent=4)
        for block in ("camera", "capture"):
            for key, value in (exif.get(block) or {}).items():
                ui.kv(key.replace("_", " "), _truncate(value, 56), indent=4)

    gps = exif.get("gps") or {}
    if gps.get("present"):
        ui.section("GPS")
        for key, value in gps.items():
            if key == "present":
                continue
            ui.kv(key.replace("_", " "), _truncate(value, 56), indent=4)
        if gps.get("latitude") is not None:
            ui.line("Resolve it:  myrecon geo " + str(gps.get("latitude")) +
                    " " + str(gps.get("longitude")), indent=4, style="grey")

    signals = data.get("signals") or []
    if signals:
        ui.section("Provenance signals")
        for signal in signals:
            if not isinstance(signal, dict):
                ui.bullet(str(signal), indent=4)
                continue
            label = signal.get("label") or signal.get("code") or ""
            confidence = signal.get("confidence")
            ui.bullet(str(label) + (ui.paint("   " + str(confidence), "grey")
                                    if confidence else ""), indent=4)
            if signal.get("detail"):
                ui.wrapped(str(signal["detail"]), indent=8)


def geo_report(data: dict) -> None:
    place = data.get("place") or {}
    coords = data.get("coordinates") or {}
    ui.heading("Place from coordinates",
               str(coords.get("latitude", "")) + ", " + str(coords.get("longitude", "")))
    ui.line("Resolved from the coordinates themselves — no landmark recognition.",
            indent=2, style="grey")

    if data.get("error") or place.get("error"):
        ui.note(str(data.get("error") or place.get("error")))

    ui.kv("name", place.get("name"))
    ui.kv("address", _truncate(place.get("display_name"), 68))
    ui.kv("category", " / ".join(x for x in [place.get("category"),
                                             place.get("type")] if x))
    for key, value in (place.get("address") or {}).items():
        ui.kv(key.replace("_", " "), value, indent=4)
    ui.kv("wikidata", place.get("wikidata"))
    ui.kv("openstreetmap", (place.get("osm") or {}).get("url"))
    ui.kv("map", (coords.get("maps") or {}).get("openstreetmap"))

    confidence = data.get("confidence") or {}
    if confidence:
        score = confidence.get("score")
        ui.kv("confidence", ui.paint(str(score) + "/100  " +
                                     str(confidence.get("band", "")),
                                     _confidence_style(score)))

    article = data.get("article") or {}
    if article:
        ui.section("Wikipedia")
        ui.kv("title", article.get("title"), indent=4)
        ui.kv("description", article.get("description"), indent=4)
        if article.get("extract"):
            ui.wrapped(str(article["extract"]), indent=4)
        ui.kv("url", article.get("url"), indent=4)

    nearby = data.get("nearby") or []
    if nearby:
        ui.section("Nearby notable places")
        ui.table(["place", "distance"],
                 [[_truncate(item.get("title"), 44),
                   str(item.get("distance_m", "")) + " m"] for item in nearby[:10]],
                 indent=4)


# ── Investigation ────────────────────────────────────────────────

def investigate_report(data: dict) -> None:
    ui.heading("Investigation", str(data.get("handle", "")))

    assessment = data.get("assessment") or {}
    if assessment.get("text"):
        ui.section("Assessment")
        ui.wrapped(str(assessment["text"]), indent=4)
        confidence = assessment.get("confidence") or {}
        if confidence:
            ui.kv("confidence", ui.paint(str(confidence.get("score")) + "/100  " +
                                         str(confidence.get("band", "")),
                                         _confidence_style(confidence.get("score"))),
                  indent=4)
        if assessment.get("generated_by"):
            ui.line(str(assessment["generated_by"]), indent=4, style="grey")

    graph = data.get("graph") or {}
    summary = graph.get("summary") or {}
    if summary:
        ui.section("Graph")
        ui.kv("entities", summary.get("entities"), indent=4)
        ui.kv("relationships", summary.get("relationships"), indent=4)
        ui.kv("clusters", summary.get("clusters"), indent=4)
        by_type = summary.get("by_type") or {}
        for entity_type, count in by_type.items():
            ui.kv("  " + str(entity_type), count, indent=4)

    clusters = graph.get("clusters") or []
    if clusters:
        ui.section("Clusters")
        for cluster in clusters[:5]:
            confidence = cluster.get("confidence") or {}
            score = confidence.get("score")
            ui.line(ui.paint(str(score).rjust(3) + "/100", _confidence_style(score)) +
                    "  " + str(cluster.get("size", "")) + " entities  " +
                    ui.paint(str(confidence.get("band", "")), "grey"), indent=4)
            for factor in (confidence.get("factors") or [])[:3]:
                ui.bullet(str(factor.get("name", "")).replace("_", " "),
                          indent=8, style="grey")

    for item in data.get("notes") or []:
        ui.note(str(item))
