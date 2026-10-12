"""Synthetic contract tests for optional public profile providers."""
import json

import pytest

from modules.email_public_profiles import (
    bounded_json, enrich_google_reviews, enrich_linkedin_email,
    google_contributor_id, normalize_google_reviews, normalize_linkedin,
)

EMAIL = "fixture@example.com"
CONTRIBUTOR = "100000000000000000001"


class Reply:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.closed = payload, status, False

    def iter_content(self, size):
        yield json.dumps(self.payload).encode()

    def close(self):
        self.closed = True


def linkedin_payload():
    return {"status": 200, "likelihood": 6, "matched": ["email"], "data": {
        "full_name": "Example Person", "linkedin_url": "linkedin.com/in/example", "linkedin_connections": 0,
        "emails": [{"address": EMAIL}], "summary": "Example biography", "location_locality": "Example City",
        "experience": [{"company": {"name": "Example Company", "password": "PRIVATE"}, "title": {"name": "Engineer"}, "start_date": "2020-01", "summary": "Example role"}],
        "education": [{"school": {"name": "Example School"}, "degrees": ["Example Degree"], "majors": ["Example Subject"], "start_date": "2016"}],
        "password": "PRIVATE", "mobile_phone": "PRIVATE", "location_street_address": "PRIVATE"}}


def test_linkedin_projects_nested_fields_and_never_forwards_private_extras():
    profile = normalize_linkedin(linkedin_payload(), EMAIL)
    assert profile["url"] == "https://linkedin.com/in/example"
    assert profile["fields"]["Connections"] == "0"
    assert profile["positions"][0]["title"] == "Engineer"
    assert "current" not in profile["positions"][0]
    assert profile["education"][0]["field_of_study"] == "Example Subject"
    assert "PRIVATE" not in str(profile)
    assert profile["avatar_url"] == ""


@pytest.mark.parametrize("mutation", ["email", "matched", "likelihood", "url"])
def test_linkedin_rejects_unproven_association(mutation):
    payload = linkedin_payload()
    if mutation == "email": payload["data"]["emails"] = [{"address": "someone@example.com"}]
    if mutation == "matched": payload["matched"] = ["name"]
    if mutation == "likelihood": payload["likelihood"] = 2
    if mutation == "url": payload["data"]["linkedin_url"] = "https://linkedin.com.evil.example/in/example"
    assert normalize_linkedin(payload, EMAIL) is None


def test_linkedin_transport_and_missing_credentials(monkeypatch):
    monkeypatch.delenv("PDL_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_LINKEDIN_ENRICHMENT_ENABLED", "true")
    monkeypatch.setattr("modules.email_public_profiles.requests.get", lambda *a, **kw: pytest.fail("No credentials"))
    assert enrich_linkedin_email(EMAIL)["status"] == "unconfigured"
    monkeypatch.setenv("PDL_API_KEY", "test-only")
    reply = Reply(linkedin_payload())
    def get(endpoint, **kwargs):
        assert endpoint == "https://api.peopledatalabs.com/v5/person/enrich"
        assert kwargs["params"]["email"] == EMAIL
        assert kwargs["params"]["min_likelihood"] == 6
        assert kwargs["params"]["include_if_matched"] == "true"
        assert kwargs["headers"] == {"X-Api-Key": "test-only"}
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        return reply
    monkeypatch.setattr("modules.email_public_profiles.requests.get", get)
    result = enrich_linkedin_email(EMAIL)
    assert result["status"] == "ok" and len(result["profiles"]) == 1
    assert reply.closed
    assert "test-only" not in str(result)


@pytest.mark.parametrize("status,expected", [(401, "authentication_required"), (404, "ok"), (429, "rate_limited"), (302, "unavailable")])
def test_linkedin_errors_are_not_profiles(monkeypatch, status, expected):
    monkeypatch.setenv("PDL_API_KEY", "test-only")
    monkeypatch.setenv("EMAIL_LINKEDIN_ENRICHMENT_ENABLED", "true")
    reply = Reply({"error": "PRIVATE"}, status)
    monkeypatch.setattr("modules.email_public_profiles.requests.get", lambda *a, **kw: reply)
    result = enrich_linkedin_email(EMAIL)
    assert result["status"] == expected and result["profiles"] == [] and reply.closed
    assert "PRIVATE" not in str(result)


def google_profile():
    return {"platform": "Google", "basis": "provider_email", "profile_status": "ok", "fields": {"ID": CONTRIBUTOR}, "reviews": []}


def google_payload():
    return {"search_metadata": {"status": "Success"}, "search_parameters": {"contributor_id": CONTRIBUTOR},
            "contributor": {"name": "Example Person", "thumbnail": "https://example.com/photo.png"},
            "reviews": [{"place_info": {"title": "Example Cafe", "address": "Example Street", "gps_coordinates": {"latitude": 10, "longitude": 20}},
                         "snippet": "Example review", "date": "3 months ago", "rating": 4, "link": "https://example.com/review", "password": "PRIVATE"}]}


def test_google_requires_source_link_and_matching_contributor():
    p = google_profile()
    assert google_contributor_id(p) == CONTRIBUTOR
    p["basis"] = "candidate"
    assert google_contributor_id(p) == ""
    result = normalize_google_reviews(google_payload(), CONTRIBUTOR)
    assert result["reviews"][0]["latitude"] == 10
    assert result["reviews"][0]["date_label"] == "3 months ago"
    assert "date" not in result["reviews"][0]
    assert "PRIVATE" not in str(result)
    with pytest.raises(ValueError): normalize_google_reviews(google_payload(), "100000000000000000002")


def test_google_request_is_bounded_and_no_guess_occurs(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-only")
    monkeypatch.setenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "true")
    reply = Reply(google_payload())
    def get(endpoint, **kwargs):
        assert endpoint == "https://serpapi.com/search.json"
        assert kwargs["params"]["contributor_id"] == CONTRIBUTOR
        assert kwargs["params"]["num"] == 100
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        return reply
    monkeypatch.setattr("modules.email_public_profiles.requests.get", get)
    result = enrich_google_reviews({"profiles": [google_profile()], "sources": []})
    assert len(result["profiles"][0]["reviews"]) == 1 and reply.closed
    assert result["sources"][0]["status"] == "ok"
    p = google_profile(); p["fields"] = {}
    monkeypatch.setattr("modules.email_public_profiles.requests.get", lambda *a, **kw: pytest.fail("No guessed IDs"))
    assert enrich_google_reviews({"profiles": [p]})["sources"][0]["status"] == "unknown"


def test_bounded_json_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr("modules.email_public_profiles.MAX_BYTES", 10)
    with pytest.raises(ValueError): bounded_json(Reply({"too": "large"}))


def test_google_documented_owner_response_and_contribution_counts(monkeypatch):
    payload = google_payload()
    payload["reviews"][0]["response"] = {"snippet": "Example owner response", "date": "a week ago", "private_token": "PRIVATE"}
    payload["contributor"]["contributions"] = {"reviews": 8, "ratings": 0, "answers": 2, "photos": 3, "private_token": "PRIVATE"}
    details = normalize_google_reviews(payload, CONTRIBUTOR)
    assert details["reviews"][0]["owner_reply"] == "Example owner response"
    assert details["reviews"][0]["owner_reply_date"] == "a week ago"
    assert details["stats"] == {"Reviews": 8, "Ratings": 0, "Answers": 2, "Photos": 3}
    assert details["limited"] is True  # Count exceeds retrieved records, even below the 100-record cap.
    assert "PRIVATE" not in str(details)
    monkeypatch.setenv("SERPAPI_API_KEY", "test-only")
    monkeypatch.setenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "true")
    monkeypatch.setattr("modules.email_public_profiles.requests.get", lambda *a, **kw: Reply(payload))
    result = enrich_google_reviews({"profiles": [google_profile()]})
    assert result["profiles"][0]["stats"]["Ratings"] == 0
    assert result["sources"][0]["status"] == "partial"


@pytest.mark.parametrize("invalid", [True, -1, "3", None, {"value": 3}])
def test_google_contribution_counts_reject_invalid_types(invalid):
    payload = google_payload()
    payload["contributor"]["contributions"] = {"reviews": invalid}
    assert normalize_google_reviews(payload, CONTRIBUTOR)["stats"] == {}


def test_bounded_json_checks_request_deadline_and_chunk_deadline(monkeypatch):
    monkeypatch.setattr("modules.email_public_profiles.time.monotonic", lambda: 30)
    with pytest.raises(ValueError, match="time limit"):
        bounded_json(Reply({}), deadline=20)
    ticks = iter([0, 1, 21])
    monkeypatch.setattr("modules.email_public_profiles.time.monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="time limit"):
        bounded_json(Reply({}))
