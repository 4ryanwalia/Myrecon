"""Public review fallback, bounded identity fanout and report preservation."""
import pytest

from modules.email_public_profiles import enrich_google_reviews
from modules.email_evidence import build_email_evidence

ID = "100000000000000000001"


def profile(contributor=ID):
    return {"platform": "Google", "basis": "provider_email", "profile_status": "ok",
            "url": "https://www.google.com/maps/contrib/" + contributor,
            "fields": {"ID": contributor}, "reviews": [], "stats": {},
            "source": "Fixture identity source", "evidence": "Exact email lookup"}


def details(contributor, status="ok"):
    return {"status": status, "contributor_id": contributor,
            "reviews": [{"name": "Example venue", "rating": 4, "source_url":
                         "https://www.google.com/maps/contrib/" + contributor}],
            "stats": {"Reviews": 0, "Ratings": 1}, "limited": False,
            "source": "Google Maps public contributions", "reason": "Public contribution records",
            "display_name": "Example public name", "returned": 1, "limit": 100}


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setenv("EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED", "true")
    monkeypatch.setenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "false")
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)


def test_free_lookup_preserves_review_and_rating_metadata_in_evidence(monkeypatch):
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", details)
    data = enrich_google_reviews({"profiles": [profile()], "sources": []})
    google = data["profiles"][0]
    assert google["review_coverage"]["status"] == "ok"
    assert google["review_coverage"]["total_reported"] == 0
    assert google["review_coverage"]["ratings_reported"] == 1
    assert google["review_coverage"]["contributions_reported"] == 1
    evidence = build_email_evidence({"profile_enrichment": data})
    assert evidence["profiles"][0]["review_coverage"] == google["review_coverage"]
    assert evidence["profiles"][0]["reviews"][0]["rating"] == 4


def test_duplicate_google_id_uses_one_request_and_distinct_ids_are_bounded(monkeypatch):
    calls = []
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews",
                        lambda contributor: calls.append(contributor) or details(contributor))
    second, third = "100000000000000000002", "100000000000000000003"
    data = enrich_google_reviews({"profiles": [profile(), profile(), profile(second), profile(third)]})
    assert calls == [ID, second]
    assert data["profiles"][0]["reviews"] == data["profiles"][1]["reviews"]
    assert data["profiles"][0]["reviews"] is not data["profiles"][1]["reviews"]
    assert data["profiles"][3]["review_coverage"]["status"] == "skipped"


def test_no_guessed_identity_and_no_requery_of_returned_collection(monkeypatch):
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", lambda *a: pytest.fail("No request"))
    candidate = profile(); candidate["basis"] = "candidate"
    existing = profile(); existing["reviews"] = [{"name": "Existing venue"}]
    result = enrich_google_reviews({"profiles": [candidate, existing]})
    assert result["profiles"][0]["review_coverage"]["status"] == "unknown"
    assert result["profiles"][1]["reviews"] == [{"name": "Existing venue"}]


def test_paid_failure_diagnostic_retained_when_public_source_succeeds(monkeypatch):
    monkeypatch.setenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "true")
    monkeypatch.setenv("SERPAPI_API_KEY", "fixture-only")
    def paid(local):
        local["sources"].append({"name": "Google Maps public reviews", "provider": "SerpApi", "status": "rate_limited"})
        return local
    monkeypatch.setattr("modules.email_public_profiles._enrich_google_reviews_serpapi", paid)
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", details)
    result = enrich_google_reviews({"profiles": [profile()]})
    assert [s["status"] for s in result["sources"]] == ["rate_limited", "ok"]
    assert result["profiles"][0]["review_coverage"]["status"] == "ok"
    assert "fixture-only" not in str(result)


def test_blocked_public_review_lookup_retains_google_identity(monkeypatch):
    def blocked(contributor):
        return {**details(contributor), "reviews": [], "stats": {}, "status": "rate_limited"}
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", blocked)
    result = enrich_google_reviews({"profiles": [profile()]})
    assert result["profiles"][0]["fields"]["ID"] == ID
    assert result["profiles"][0]["review_coverage"]["status"] == "rate_limited"
    assert result["profiles"][0]["review_coverage"]["total_reported"] is None


def test_duplicate_identity_retains_conflicting_source_counts(monkeypatch):
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", details)
    first, second = profile(), profile()
    first["stats"] = {"Reviews": 2, "Ratings": 0}
    second["stats"] = {"Reviews": 8, "Ratings": 1}
    result = enrich_google_reviews({"profiles": [first, second]})
    assert result["profiles"][0]["stats"]["Reviews"] == 2
    assert result["profiles"][1]["stats"]["Reviews"] == 8
    assert result["profiles"][1]["review_coverage"]["total_reported"] == 0
    assert result["profiles"][1]["review_coverage"]["ratings_reported"] == 1
    assert result["profiles"][1]["review_coverage"]["status"] == "ok"
    assert len(result["profiles"][1]["field_conflicts"]["stats.Reviews"]) == 2


def test_existing_review_collection_reports_missing_known_contributions(monkeypatch):
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", lambda *a: pytest.fail("Keep provider collection"))
    p = profile(); p["reviews"] = [{"name": "Example venue", "rating": 5}]
    p["stats"] = {"Reviews": 2, "Ratings": 1}
    result = enrich_google_reviews({"profiles": [p]})
    assert result["profiles"][0]["review_coverage"]["status"] == "partial"
    assert result["profiles"][0]["review_coverage"]["contributions_reported"] == 3


def test_review_timeline_attributes_the_actual_review_source():
    p = profile(); p["review_source"] = "Google Maps public contributions"
    p["reviews"] = [{"id": "public-review-one", "name": "Example venue", "date": "2020-01-01T00:00:00Z"}]
    report = build_email_evidence({"profile_enrichment": {"profiles": [p]}})
    event = next(e for e in report["timeline"] if e["title"].startswith("Review:"))
    assert event["sources"] == ["Google Maps public contributions"]


def test_distinct_public_review_ids_are_not_merged_by_matching_text():
    first, second = profile(), profile()
    body = {"name": "Example venue", "address": "Example street", "text": "Example text", "date": "2020-01-01T00:00:00Z"}
    first["reviews"] = [{**body, "id": "public-review-one"}]
    second["reviews"] = [{**body, "id": "public-review-two"}]
    report = build_email_evidence({"profile_enrichment": {"profiles": [first, second]}})
    assert len(report["profiles"][0]["reviews"]) == 2
