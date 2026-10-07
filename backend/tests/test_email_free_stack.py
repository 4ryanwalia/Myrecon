"""Independent free sources retain identity and outage boundaries in the pipeline."""
from modules import email_enrichment as enrichment
from services import email as service

EMAIL = "fixture@example.com"


def response(name, state="unconfigured", profiles=None):
    return {"status": state, "profiles": profiles or [], "registrations": [],
            "sources": [{"name": name, "status": state}]}


def test_free_google_runs_once_and_supplies_review_identity_without_paid_provider(monkeypatch):
    calls = []
    def provider(name, state="unconfigured", profiles=None):
        def run(email):
            calls.append(name)
            assert email == EMAIL
            return response(name, state, profiles)
        return run
    google = {"platform": "Google", "fields": {"ID": "100000000000000000001"},
              "basis": "provider_email", "profile_status": "ok"}
    monkeypatch.setattr(enrichment, "_enrich_osint_industries", provider("OI"))
    monkeypatch.setattr("modules.email_public_profiles.enrich_linkedin_email", provider("PDL"))
    monkeypatch.setattr("modules.email_ghunt.enrich_ghunt_email", provider("GHunt", "found", [google]))
    def reviews(result):
        assert result["profiles"][0]["fields"]["ID"] == google["fields"]["ID"]
        result["sources"].append({"name": "Reviews", "status": "rate_limited"})
        return result
    monkeypatch.setattr("modules.email_public_profiles.enrich_google_reviews", reviews)
    result = enrichment.enrich_email(EMAIL)
    assert sorted(calls) == ["GHunt", "OI", "PDL"]
    assert result["profiles"] == [google] and result["status"] == "partial"


def test_free_source_exception_does_not_erase_completed_profile(monkeypatch):
    monkeypatch.setattr(enrichment, "_enrich_osint_industries", lambda e: response("OI", "found", [{"platform": "GitHub"}]))
    monkeypatch.setattr("modules.email_public_profiles.enrich_linkedin_email", lambda e: response("PDL"))
    def broken(email):
        raise RuntimeError("PRIVATE_TOKEN")
    monkeypatch.setattr("modules.email_ghunt.enrich_ghunt_email", broken)
    monkeypatch.setattr("modules.email_public_profiles.enrich_google_reviews", lambda r: r)
    result = enrichment.enrich_email(EMAIL)
    assert result["profiles"] and result["status"] == "partial"
    assert "PRIVATE_TOKEN" not in str(result)


def test_public_link_reader_receives_completed_github_and_failures_remain_visible(monkeypatch):
    github = {"status": "found", "username": "example", "url": "https://github.com/example",
              "website": "https://www.linkedin.com/in/example"}
    monkeypatch.setattr(service.EmailLookup, "scan", lambda *a, **k: {"github": github})
    monkeypatch.setattr(service, "enrich_email", lambda e: response("GHunt", "found"))
    monkeypatch.setattr(service, "breach_details", lambda e: {"status": "unconfigured", "records": []})
    def public_reader(result, established):
        assert established is github
        result["sources"].append({"name": "LinkedIn public profile", "status": "blocked"})
    monkeypatch.setattr(service, "enrich_linkedin_public", public_reader)
    result = service.scan_email(EMAIL, True)
    assert result["partial"] and result["evidence_report"]["profiles"][0]["username"] == "example"
    assert result["profile_enrichment"]["status"] == "partial"


def test_skipped_email_checks_do_not_run_free_sources(monkeypatch):
    monkeypatch.setattr(service.EmailLookup, "scan", lambda *a, **k: {})
    def forbidden(*a, **k):
        raise AssertionError("Opt-in is required")
    monkeypatch.setattr(service, "enrich_email", forbidden)
    monkeypatch.setattr(service, "enrich_linkedin_public", forbidden)
    assert service.scan_email(EMAIL, False)["profile_enrichment"]["status"] == "skipped"
