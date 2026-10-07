"""Email intelligence service layer, thin, JSON-safe wrapper."""

from modules.email_lookup import EmailLookup, _COMPILATION
from modules.email_evidence import build_email_evidence
from modules.email_enrichment import enrich_email, summarize_enrichment
from modules.email_linkedin_public import enrich_linkedin_public
from modules.email_breach_details import breach_details
from modules.email_platform_summary import build_platform_summary, canonical_platform
from concurrent.futures import ThreadPoolExecutor
from modules.user_scanner import scan_selected


def _optional_source(call, email, empty, source):
    """Optional-source failures never erase completed lookup findings."""
    try:
        result = call(email)
        if isinstance(result, dict) and isinstance(result.get("status"), str):
            normalized = {**empty, **result}
            if all(isinstance(normalized[key], type(value)) for key, value in empty.items()):
                return normalized
    except Exception:
        pass  # Provider exception text can contain the query or credentials.
    return {**empty, "status": "unavailable", "message": source + " could not return usable results; other findings retained."}


def _merge_enrichment_links(result):
    """Keep profile/provider/registration/historical evidence distinct."""
    services = result.setdefault("linked_services", {"services": []})
    canonical = lambda name: canonical_platform(name)[0]
    rows = {}

    def retain_history(target, historical):
        item = {field: historical.get(field, "") for field in ("evidence", "date", "url", "source")}
        if item not in target.setdefault("historical_evidence", []):
            target["historical_evidence"].append(item)

    for old in services.get("services", []):
        if not isinstance(old, dict) or not old.get("service"):
            continue
        ident = canonical(old["service"])
        if not ident:
            continue
        if ident not in rows:
            rows[ident] = dict(old)
        elif old.get("kind") == "breach":
            retain_history(rows[ident], old)
        elif rows[ident].get("kind") == "breach":
            historical = rows[ident]
            rows[ident] = dict(old)
            retain_history(rows[ident], historical)
        elif old.get("kind") == "registration":
            rows[ident].update(registration_status="found", registration_evidence=old.get("evidence", ""),
                               registration_source=old.get("source", ""))
        elif rows[ident].get("kind") == "registration" and old.get("kind") == "profile":
            previous = rows[ident]
            rows[ident] = dict(old)
            rows[ident].update(registration_status="found", registration_evidence=previous.get("evidence", ""),
                               registration_source=previous.get("source", ""))
    enrichment = result["profile_enrichment"]
    for profile in enrichment.get("profiles", []):
        if not isinstance(profile, dict) or not profile.get("platform"):
            continue
        ident = canonical(profile["platform"])
        if not ident:
            continue
        projection = {"service": profile["platform"], "kind": "profile", "basis": profile.get("basis", "provider_email"),
                      "url": profile.get("url", ""), "evidence": profile.get("evidence", "Source-reported profile association"),
                      "source": profile.get("source", "")}
        if ident not in rows:
            rows[ident] = projection
        elif rows[ident].get("kind") == "breach":
            historical = dict(rows[ident])
            rows[ident].update(projection)
            retain_history(rows[ident], historical)
        elif rows[ident].get("kind") == "registration":
            rows[ident].update(registration_status="found", registration_evidence=rows[ident].get("evidence", ""),
                               registration_source=rows[ident].get("source", ""))
            rows[ident].update(projection)
    for registration in enrichment.get("registrations", []):
        if not isinstance(registration, dict) or registration.get("status") != "found" or not registration.get("service"):
            continue
        ident = canonical(registration["service"])
        if ident in rows:
            rows[ident].update(registration_status="found", registration_evidence=registration.get("reason", ""),
                               registration_source=registration.get("source", ""))
        else:
            rows[ident] = {"service": registration["service"], "kind": "registration", "basis": "registration_signal", "url": "",
                           "evidence": registration.get("reason", ""), "source": registration.get("source", "")}
    for record in result["breach_details"].get("records", []):
        if not isinstance(record, dict) or not record.get("name") or record.get("compilation") or _COMPILATION.search(record["name"]):
            continue
        ident = canonical(record["name"])
        if ident not in rows:
            rows[ident] = {"service": record["name"], "kind": "breach", "date": record.get("date", ""), "url": "", "evidence": "Historical record reported by LeakCheck Pro"}
        else:
            retain_history(rows[ident], {"date": record.get("date", ""), "evidence": "Historical record reported by LeakCheck Pro", "source": "LeakCheck Pro"})
    ordered = sorted(rows.values(), key=lambda r: (r["kind"] == "breach", r["service"].lower()))
    services.update(services=ordered, count=len(ordered), from_profiles=sum(r["kind"] == "profile" for r in ordered),
                    from_breaches=sum(r["kind"] == "breach" for r in ordered),
                    from_registration=sum(r["kind"] == "registration" or r.get("registration_status") == "found" for r in ordered))
    summary = result.setdefault("summary", {})
    summary["linked_services_count"] = len(ordered)
    summary["linked_accounts"] = sorted(set(summary.get("linked_accounts", [])) | {p["platform"] for p in enrichment.get("profiles", []) if isinstance(p, dict) and p.get("platform")})


def scan_email(email: str, check_linked_accounts: bool = False) -> dict:
    """Run the reliable email-intelligence pipeline and return JSON-safe data."""
    lookup = EmailLookup()
    if check_linked_accounts:
        # The bounded provider request overlaps the existing lookup work.
        with ThreadPoolExecutor(max_workers=3) as workers:
            enriched = workers.submit(_optional_source, enrich_email, email,
                                      {"profiles": [], "registrations": [], "sources": []}, "Profile enrichment")
            detailed = workers.submit(_optional_source, breach_details, email,
                                      {"records": [], "checked": False, "breached": False}, "LeakCheck Pro")
            result = lookup.scan(email, check_linked_accounts=True)
            result["profile_enrichment"] = enriched.result()
            result["breach_details"] = detailed.result()
        # URL-based public reading follows the completed exact-email sources.
        try:
            enrich_linkedin_public(result["profile_enrichment"], result.get("github"))
        except Exception:
            result["profile_enrichment"]["sources"].append({"name": "LinkedIn public profile", "status": "unavailable"})
        summarize_enrichment(result["profile_enrichment"])
    else:
        result = lookup.scan(email, check_linked_accounts=False)
        result["profile_enrichment"] = {"status": "skipped", "profiles": [], "registrations": [], "sources": []}
        result["breach_details"] = {"status": "skipped", "records": [], "checked": False, "breached": False}
    enrichment = result["profile_enrichment"]
    checks = result.setdefault("account_checks", {})
    checks.setdefault("enabled", check_linked_accounts)
    checks.setdefault("sources", []).append({"name": "Profile enrichment", "status": enrichment["status"]})
    if enrichment["status"] not in ("ok", "skipped", "unconfigured"):
        result["partial"] = True
        result.setdefault("errors", []).append({"source": "Profile enrichment", "code": enrichment["status"], "message": enrichment.get("message", "Profile enrichment unavailable; other findings retained."), "retryable": True})
    details = result["breach_details"]
    if details["status"] not in ("skipped", "unconfigured"):
        coverage = result.setdefault("summary", {}).setdefault("breach_coverage", {}).setdefault("sources", [])
        coverage.append({"name": "LeakCheck Pro", "status": details["status"], "checked": details.get("checked", False)})
        if details.get("breached"):
            result["summary"]["breached"] = True
        if details["status"] != "ok":
            result["partial"] = True
            result.setdefault("errors", []).append({"source": "LeakCheck Pro", "code": details["status"], "message": details.get("message"), "retryable": True})
        attempted = [s for s in coverage if s["status"] not in ("skipped", "unconfigured")]
        completed = sum(s["status"] == "ok" and s.get("checked", True) for s in attempted)
        summary = result["summary"]
        summary["breach_coverage"].update(completed=completed, attempted=len(attempted))
        summary["breach_status"] = "ok" if completed == len(attempted) else "partial_unavailable" if completed else "unavailable"
        summary["breach_outcome"] = "found" if summary.get("breached") else "unavailable" if not completed else "incomplete" if completed < len(attempted) else "no_match"
        summary["records_found"] = max(summary.get("records_found", 0), details.get("reported_rows", 0))
    _merge_enrichment_links(result)
    result["evidence_report"] = build_email_evidence(result)
    result["platform_summary"] = build_platform_summary(result)
    result.setdefault("summary", {})["linked_platforms_count"] = result["platform_summary"]["counts"]["linked_platforms"]
    if details.get("breached"):
        result["summary"]["breach_count"] = max(result["summary"].get("breach_count", 0), result["evidence_report"]["counts"]["named_breaches"])
    result["status"] = "ok"
    # Foundation diagnostics only. Existing paid/account gates remain in
    # charge; a later reviewed integration must explicitly authorize workers.
    result["user_scanner"] = scan_selected(email, "email", permitted=False)
    return result
