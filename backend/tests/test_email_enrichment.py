"""Rich provider contract and evidence tests; synthetic input only, no network."""
import json
import pytest
from modules.email_enrichment import enrich_email, normalize_response
from modules.email_evidence import build_email_evidence

EMAIL = "fixture@example.com"


def wrapped(value):
    return {"value": value, "type": "str"}


def module(platform, **values):
    return {"module": platform, "query": EMAIL, "status": "found", "spec_format": [
        {"registered": wrapped(True), **{k: wrapped(v) for k, v in values.items()}}]}


def rich_module(platform, variables, **values):
    result = module(platform, **values)
    result["spec_format"][0]["platform_variables"] = [{"key": k, "value": v} for k, v in variables.items()]
    return result


def test_google_reviews_venues_linkedin_jobs_and_false_flags_are_projected():
    payload = [rich_module("Google", {"enterprise_user": False, "active_google_apps": ["Maps", "Photos"], "reviews_count": 0,
        "reviews": [{"place_name": "Example cafe", "address": "Example street", "rating": 4.5,
                     "review_text": "Example review", "relative_date": "3 weeks ago", "date": "2024-03-02",
                     "latitude": 10, "longitude": 20, "owner_reply": "Thank you", "owner_reply_date": "2 weeks ago",
                     "source_url": "https://example.com/review", "password": "DO_NOT_FORWARD"}]}, name="Example", id="123", last_seen="2024-04-01"),
        rich_module("LinkedIn", {"connections": 500, "positions": [{"title": "Engineer", "company": "Example", "start": "2023-12", "current": True}],
                                  "education": [{"school": "Example school", "start": "2016", "end": "2020"}]}, username="example", location="Declared city"),
        rich_module("Wix", {"email_verified": False, "blocked": False, "auth_methods": ["google"]}, id="uuid")]
    enrichment = normalize_response(payload, EMAIL)
    google, linkedin, wix = enrichment["profiles"]
    assert google["fields"]["Enterprise user"] == "No"
    assert google["stats"]["Reviews"] == 0
    assert google["reviews"][0]["rating"] == 4.5
    assert "DO_NOT_FORWARD" not in str(enrichment)
    assert linkedin["positions"][0]["current"] is True
    assert wix["fields"]["Email verified"] == "No"
    report = build_email_evidence({"profile_enrichment": enrichment})
    venue = next(r for r in report["locations"] if r["basis"] == "review_venue")
    assert venue["url"] == "https://www.google.com/maps?q=10.0,20.0"
    assert venue["value"] == "Example street"
    assert report["counts"]["registration_signals"] == 3
    assert report["latest"]["title"] == "Google last seen"


def test_registration_only_breach_pivots_and_missing_queries_are_not_profiles():
    bare = module("Spotify")
    pivot = module("LinkedIn", username="other"); pivot["query"] = "other@example.com"
    missing = module("Google", name="unknown"); missing.pop("query")
    breach = module("hibp", breach=True, name="Example breach")
    result = normalize_response([bare, pivot, missing, breach], EMAIL)
    assert result["profiles"] == []
    assert [r["service"] for r in result["registrations"]] == ["Spotify"]


def test_urls_secrets_and_invalid_coordinates_do_not_escape_the_adapter():
    row = rich_module("Google", {"password": "SECRET", "token": "SECRET", "reviews": [
        {"name": "Example", "lat": 999, "lng": "nan", "rating": 90, "url": "javascript:alert(1)"}]},
        username="example", profile_url="https://user:password@example.com", picture_url="javascript:alert(2)")
    result = normalize_response([row], EMAIL)
    p = result["profiles"][0]
    assert p["url"] == p["avatar_url"] == ""
    assert p["reviews"] == [{"name": "Example"}]
    assert "SECRET" not in str(result)


def test_unconfigured_never_calls_provider_or_sandbox(monkeypatch):
    monkeypatch.delenv("OSINT_INDUSTRIES_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_ENRICHMENT_ENABLED", "true")
    monkeypatch.setattr("modules.email_enrichment.requests.post", lambda *a, **kw: pytest.fail("No request allowed"))
    assert enrich_email(EMAIL)["status"] == "unconfigured"
    monkeypatch.setenv("OSINT_INDUSTRIES_API_KEY", "test-only-key")
    monkeypatch.setenv("EMAIL_ENRICHMENT_ENABLED", "false")
    assert enrich_email(EMAIL)["profiles"] == []


@pytest.mark.parametrize("http,state", [(401, "authentication_required"), (402, "credits_exhausted"), (429, "rate_limited"), (500, "unavailable"), (302, "unavailable")])
def test_provider_errors_use_status_without_forwarding_body_or_key(monkeypatch, http, state):
    monkeypatch.setenv("OSINT_INDUSTRIES_API_KEY", "test-only-key")
    monkeypatch.setenv("EMAIL_ENRICHMENT_ENABLED", "true")
    class Reply:
        status_code = http
        closed = False
        def close(self): self.closed = True
    response = Reply()
    monkeypatch.setattr("modules.email_enrichment.requests.post", lambda *a, **kw: response)
    r = enrich_email(EMAIL)
    assert r["status"] == state and r["profiles"] == []
    assert "test-only-key" not in str(r)
    assert response.closed


def test_documented_post_contract_and_unreadable_response(monkeypatch):
    monkeypatch.setenv("OSINT_INDUSTRIES_API_KEY", "test-only-key")
    monkeypatch.setenv("EMAIL_ENRICHMENT_ENABLED", "true")
    class Reply:
        status_code = 200
        closed = False
        payload = [module("Github", username="example")]
        def iter_content(self, size): yield json.dumps(self.payload).encode()
        def close(self): self.closed = True
    responses = []
    def post(endpoint, **kwargs):
        assert endpoint == "https://api.osint.industries/v2/request"
        assert kwargs["json"] == {"type": "email", "query": EMAIL, "timeout": 25, "premium": False}
        assert kwargs["headers"]["api-key"] == "test-only-key"
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        response = Reply(); responses.append(response)
        return response
    monkeypatch.setattr("modules.email_enrichment.requests.post", post)
    assert enrich_email(EMAIL)["profiles"][0]["username"] == "example"
    monkeypatch.setattr(Reply, "payload", {"error": "bad body"})
    assert enrich_email(EMAIL)["status"] == "unavailable"
    assert all(r.closed for r in responses)


def test_osint_industries_oversized_stream_is_closed(monkeypatch):
    monkeypatch.setenv("OSINT_INDUSTRIES_API_KEY", "test-only-key")
    monkeypatch.setenv("EMAIL_ENRICHMENT_ENABLED", "true")
    monkeypatch.setattr("modules.email_public_profiles.MAX_BYTES", 10)
    class Reply:
        status_code = 200
        closed = False
        def iter_content(self, size): yield b"[" * 11
        def close(self): self.closed = True
    reply = Reply()
    monkeypatch.setattr("modules.email_enrichment.requests.post", lambda *a, **kw: reply)
    result = enrich_email(EMAIL)
    assert result["status"] == "unavailable" and result["profiles"] == [] and reply.closed


def test_provider_failure_preserves_successful_existing_sources(monkeypatch):
    from services import email as service
    monkeypatch.setattr(service.EmailLookup, "scan", lambda *a, **kw: {"github": {"status": "found", "username": "dev"}, "errors": []})
    monkeypatch.setattr(service, "enrich_email", lambda e: {"status": "rate_limited", "profiles": [], "registrations": []})
    result = service.scan_email(EMAIL, True)
    assert result["partial"] is True
    assert result["evidence_report"]["profiles"][0]["username"] == "dev"


def test_duplicate_github_profiles_merge_details_but_preserve_historical_basis():
    enrichment = normalize_response([module("GitHub", username="dev", profile_url="https://github.com/dev", id="12")], EMAIL)
    report = build_email_evidence({"github": {"status": "found", "username": "dev", "url": "https://github.com/dev", "evidence_url": "https://github.com/dev/repo/commit/1"}, "profile_enrichment": enrichment})
    assert len(report["profiles"]) == 1
    assert report["profiles"][0]["basis"] == "historical_commit"
    assert report["profiles"][0]["fields"]["ID"] == "12"


def test_service_links_merge_provider_signals_without_upgrading_historical_basis():
    from services.email import _merge_enrichment_links
    result = {"linked_services": {"services": [{"service": "GitHub", "kind": "profile", "basis": "historical_commit"}, {"service": "Twitter", "kind": "registration"}]},
              "profile_enrichment": normalize_response([module("GitHub", username="dev", profile_url="https://github.com/dev"), module("Google", name="Example"), module("twitter")], EMAIL),
              "breach_details": {"records": [{"name": "Collection1", "compilation": True}, {"name": "Canva", "date": "2019-04"}]}}
    _merge_enrichment_links(result)
    rows = result["linked_services"]["services"]
    assert len(rows) == 4
    assert next(r for r in rows if r["service"] == "GitHub")["basis"] == "historical_commit"
    assert next(r for r in rows if r["service"] == "Google")["basis"] == "provider_email"
    assert next(r for r in rows if r["service"] == "Twitter")["registration_status"] == "found"
    assert "Collection1" not in str(rows)


def test_nested_public_presentation_shapes_and_partial_provider_diagnostics():
    payload = [rich_module("Google", {"google_reviews": [{"location": {"name": "Example Cafe", "address": "Example Street", "position": {"latitude": 10, "longitude": 20}, "link": "https://example.com/maps"}, "comment": "Example", "link": "https://example.com/review"}], "google_stats": {"reviews": 0}}),
               rich_module("LinkedIn", {"linkedin_positions": [{"title": "Engineer", "company_name": "Example", "start_year": 2020, "start_month": 2, "company_logo_url": "https://example.com/logo.png"}], "linkedin_education": [{"school_name": "Example School", "degree": "Example degree", "field_of_study": "Example subject", "end_year": 2024}]}, first_name="Example", last_name="Person")]
    result = normalize_response(payload, EMAIL)
    assert result["profiles"][0]["reviews"][0]["latitude"] == 10
    assert result["profiles"][0]["stats"]["Reviews"] == 0
    assert result["profiles"][1]["display_name"] == "Example Person"
    assert result["profiles"][1]["positions"][0]["start"] == "2020-02"
    assert "current" not in result["profiles"][1]["positions"][0]
    payload[1]["reliable_source"] = False
    assert normalize_response(payload, EMAIL)["status"] == "partial"
    assert normalize_response([], EMAIL)["status"] == "partial"


@pytest.mark.parametrize("oi_state,pdl_state,positive_source,expected", [
    ("ok", "rate_limited", "oi", "partial"),
    ("unavailable", "ok", "pdl", "partial"),
    ("unconfigured", "rate_limited", None, "rate_limited"),
    ("unconfigured", "ok", "pdl", "partial"),
])
def test_independent_provider_failure_aggregation(monkeypatch, oi_state, pdl_state, positive_source, expected):
    oi = {"status": oi_state, "sources": [{"name": "OSINT Industries", "status": oi_state}], "profiles": [], "registrations": []}
    pdl = {"status": pdl_state, "sources": [{"name": "LinkedIn", "status": pdl_state}], "profiles": [], "registrations": []}
    if positive_source == "oi": oi["profiles"] = [{"platform": "Google", "display_name": "Example"}]
    if positive_source == "pdl": pdl["profiles"] = [{"platform": "LinkedIn", "display_name": "Example"}]
    monkeypatch.setattr("modules.email_enrichment._enrich_osint_industries", lambda e: oi)
    monkeypatch.setattr("modules.email_public_profiles.enrich_linkedin_email", lambda e: pdl)
    result = enrich_email(EMAIL)
    assert result["status"] == expected
    assert bool(result["profiles"]) == bool(positive_source)
    assert result["message"]


@pytest.mark.parametrize("review_state", ["partial", "rate_limited", "unavailable"])
def test_google_review_failure_is_visible_in_combined_result(monkeypatch, review_state):
    oi = {"status": "ok", "profiles": [{"platform": "Google", "display_name": "Example"}], "registrations": [],
          "sources": [{"name": "Google", "status": "found"}, {"name": "Google Maps public reviews", "status": review_state}]}
    pdl = {"status": "unconfigured", "profiles": [], "registrations": [], "sources": [{"name": "LinkedIn", "status": "unconfigured"}]}
    monkeypatch.setattr("modules.email_enrichment._enrich_osint_industries", lambda e: oi)
    monkeypatch.setattr("modules.email_public_profiles.enrich_linkedin_email", lambda e: pdl)
    result = enrich_email(EMAIL)
    assert result["status"] == "partial" and result["profiles"]
