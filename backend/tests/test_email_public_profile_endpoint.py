"""Isolated Android public-profile endpoint contracts; no live provider calls."""
import json

import pytest

from services import email_public_profiles as service


EMAIL = "fixture@example.com"
ID = "100000000000000000001"


def google_profile():
    return {"platform": "Google", "basis": "provider_email", "profile_status": "ok",
            "url": f"https://www.google.com/maps/contrib/{ID}/reviews",
            "fields": {"ID": ID, "Last profile edit": "2020-01-01"},
            "display_name": "Example public contributor", "stats": {"Reviews": 1, "Ratings": 0},
            "reviews": [], "source": "GHunt"}


@pytest.fixture(autouse=True)
def isolated_adapters(monkeypatch):
    # Fail closed unless each fixture supplies its own Google identity response.
    monkeypatch.setattr(service, "enrich_ghunt_email", lambda email: pytest.fail("Unexpected identity call"))
    monkeypatch.setattr(service, "enrich_google_reviews", lambda value: value)


def identity(monkeypatch, profile=None, status="found"):
    data = {"profiles": [profile or google_profile()] if status == "found" else [],
            "sources": [{"name": "Google public profile", "provider": "GHunt", "status": status}]}
    monkeypatch.setattr(service, "enrich_ghunt_email", lambda email: data)
    return data


def completed_reviews(enrichment):
    profile = enrichment["profiles"][0]
    profile["reviews"] = [{"id": "fixture-review", "name": "Example cafe", "rating": 5,
                           "text": "Example public review", "address": "Example street",
                           "date": "2020-02-01T00:00:00Z", "owner_reply": "Example reply",
                           "source_url": f"https://www.google.com/maps/contrib/{ID}/reviews",
                           "maps_url": "https://www.google.com/maps/search/?api=1&query=Example+cafe"}]
    profile["review_source"] = "Google Maps public contributions"
    profile["review_coverage"] = {"status": "ok", "limited": False, "total_reported": 1,
                                  "ratings_reported": 0, "contributions_reported": 1,
                                  "source": "Google Maps public contributions"}
    enrichment["sources"].append({"name": "Google Maps public reviews", "provider": "Google public contributions",
                                  "status": "ok", "returned": 1, "limit": 100, "limited": False})
    return enrichment


def test_email_identity_then_public_reviews_without_unrelated_email_fanout(monkeypatch):
    calls = []
    data = identity(monkeypatch)
    monkeypatch.setattr(service, "enrich_ghunt_email", lambda email: calls.append(("identity", email)) or data)
    monkeypatch.setattr(service, "enrich_google_reviews", lambda value: calls.append(("reviews", value["profiles"][0]["fields"]["ID"])) or completed_reviews(value))
    monkeypatch.setattr("modules.email_lookup.EmailLookup.scan", lambda *a, **k: pytest.fail("No breach/account scan"))
    monkeypatch.setattr("modules.email_enrichment.enrich_email", lambda *a, **k: pytest.fail("No paid profile fanout"))
    result = service.lookup_public_profiles(EMAIL)
    assert calls == [("identity", EMAIL), ("reviews", ID)]
    assert result["status"] == "ok"
    assert result["query"] == {"email": EMAIL}
    assert result["profiles"][0]["reviews"][0]["text"] == "Example public review"
    assert result["profiles"][0]["review_coverage"]["returned"] == 1


def test_private_fields_and_raw_provider_payloads_never_leave_service(monkeypatch):
    profile = google_profile()
    profile.update(cookie="PRIVATE", token="PRIVATE", calendar="PRIVATE", emails={"CONTACT": "PRIVATE"},
                   lists={"Private app": "PRIVATE"}, last_seen="PRIVATE", raw={"session": "PRIVATE"})
    profile["fields"].update(Password="PRIVATE", **{"Last seen": "PRIVATE"})
    profile["stats"]["Private"] = "PRIVATE"
    data = identity(monkeypatch, profile)
    data.update(registrations=["PRIVATE"], credentials="PRIVATE")
    data["sources"][0].update(raw="PRIVATE", reason="PRIVATE")

    def reviews(value):
        value = completed_reviews(value)
        value["profiles"][0]["reviews"][0].update(cookie="PRIVATE", raw="PRIVATE", private_location="PRIVATE")
        value["profiles"][0]["review_coverage"].update(cookie="PRIVATE", reason="PRIVATE")
        value["sources"][-1].update(api_key="PRIVATE", reason="PRIVATE")
        return value

    monkeypatch.setattr(service, "enrich_google_reviews", reviews)
    result = service.lookup_public_profiles(EMAIL)
    assert "PRIVATE" not in json.dumps(result)
    assert set(result) == {"query", "status", "profiles", "sources"}
    assert set(result["profiles"][0]["fields"]) == {"ID", "Last profile edit"}


@pytest.mark.parametrize("state", ["disabled", "unconfigured", "authentication_required", "timeout", "rate_limited", "unavailable"])
def test_missing_access_is_never_a_negative_match(monkeypatch, state):
    identity(monkeypatch, status=state)
    result = service.lookup_public_profiles(EMAIL)
    assert result["status"] == state
    assert result["profiles"] == []
    assert result["sources"][0]["status"] == state


def test_explicit_no_match_retains_its_source_outcome(monkeypatch):
    identity(monkeypatch, status="no_match")
    result = service.lookup_public_profiles(EMAIL)
    assert result["status"] == "no_match"
    assert result["profiles"] == []


def test_review_failure_retains_the_public_google_profile(monkeypatch):
    identity(monkeypatch)

    def broken(value):
        value["profiles"][0]["display_name"] = "PRIVATE"
        raise RuntimeError("PRIVATE")

    monkeypatch.setattr(service, "enrich_google_reviews", broken)
    result = service.lookup_public_profiles(EMAIL)
    assert result["status"] == "partial"
    assert result["profiles"][0]["fields"]["ID"] == ID
    assert result["profiles"][0]["display_name"] == "Example public contributor"
    assert result["profiles"][0]["review_coverage"]["status"] == "unavailable"
    assert "PRIVATE" not in json.dumps(result)


def test_candidate_or_conflicting_google_identity_cannot_become_review_evidence(monkeypatch):
    candidate = google_profile()
    candidate["basis"] = "candidate"
    conflict = google_profile()
    conflict["fields"]["ID"] = "100000000000000000002"
    monkeypatch.setattr(service, "enrich_ghunt_email", lambda email: {"profiles": [candidate, conflict], "sources": []})
    result = service.lookup_public_profiles(EMAIL)
    assert result["profiles"] == []
    assert result["status"] == "unavailable"


def test_wrong_contributor_and_private_avatar_links_are_removed(monkeypatch):
    profile = google_profile()
    profile["avatar_url"] = "https://user:PRIVATE@lh3.googleusercontent.com/avatar"
    identity(monkeypatch, profile)

    def links(value):
        value = completed_reviews(value)
        value["profiles"][0]["reviews"][0]["source_url"] = "https://www.google.com/maps/contrib/100000000000000000002/reviews"
        value["profiles"][0]["reviews"][0]["maps_url"] = "file:///PRIVATE"
        return value

    monkeypatch.setattr(service, "enrich_google_reviews", links)
    result = service.lookup_public_profiles(EMAIL)
    profile = result["profiles"][0]
    assert profile["avatar_url"] == ""
    assert profile["reviews"][0]["source_url"] == profile["url"]
    assert "maps_url" not in profile["reviews"][0]
    assert "PRIVATE" not in json.dumps(result)


def test_public_profile_endpoint_validates_query_and_never_caches(monkeypatch):
    import app as appmod
    import config

    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    calls = []
    monkeypatch.setattr(service, "lookup_public_profiles", lambda email: calls.append(email) or {
        "status": "unconfigured", "query": {"email": email}, "profiles": [], "sources": []})
    client = appmod.create_app().test_client()
    assert client.post("/api/email/public-profiles", json={"email": "bad"}).status_code == 422
    for _ in range(2):
        response = client.post("/api/email/public-profiles", json={"email": EMAIL})
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.get_json()["status"] == "unconfigured"
    assert calls == [EMAIL, EMAIL]
    assert client.options("/api/email/public-profiles").status_code == 204
