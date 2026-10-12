"""Evidence quality scores describe source basis, never inferred ownership."""
from datetime import date, datetime, timezone
import pytest
from modules.email_quality import annotate_report, confidence, freshness
from modules.email_evidence import build_email_evidence

TODAY = date(2026, 10, 1)
NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("basis,score", [
    ("exact_public_email", 4), ("provider_email", 3), ("email_hash", 3),
    ("public_link", 2), ("historical_commit", 2), ("historical_public_link", 1),
    ("historical_breach", 1), ("registration_signal", 1), ("review_venue", 2), ("invented", 0)])
def test_fixed_rules_do_not_claim_probability(basis, score):
    row = confidence(basis)
    assert row["score"] == score and row["scale"] == 4
    assert row["method"] == "source-basis-v1"
    assert confidence(basis, True)["score"] <= 1


@pytest.mark.parametrize("reported,status", [
    ("", "unknown"), ("3 years ago", "invalid_date"), ("2024-13", "invalid_date"),
    ("2024-02-30", "invalid_date"), ("2027", "future_date"), ("2026-11", "future_date"),
    ("2026-10-02", "future_date"), ("2024", "potentially_outdated"),
    ("2025-09", "potentially_outdated"), ("2025-10", "source_reported"),
    ("2026", "source_reported"), ("2026-09-01", "source_reported"),
    ("2026-10-02T00:30:00+02:00", "source_reported")])
def test_freshness_preserves_coarse_dates_and_rejects_future_signals(reported, status):
    row = freshness("provider_email", reported, TODAY)
    assert row["status"] == status and row["as_of"] == "2026-10-01"
    if reported:
        assert row["reported_date"] == reported


def test_historical_association_stays_historical_even_with_recent_activity():
    assert freshness("historical_commit", "2026-10-01", TODAY)["status"] == "historical"
    assert freshness("historical_breach", "2026-10-01", TODAY)["status"] == "historical"


def test_creation_dates_retrieval_and_source_count_do_not_prove_recency():
    profile = {"basis": "provider_email", "created_at": "2000-01-01", "source": "Example",
               "sources": ["one", "two", "three"], "display_name": "Fixture", "platform": "Google"}
    report = annotate_report({"profiles": [profile]}, NOW)
    assert report["generated_at"] == "2026-10-01T12:00:00Z"
    assert profile["freshness"]["status"] == "unknown"
    assert profile["confidence"]["score"] == 3
    assert "not a calibrated probability" in report["confidence_note"]


def test_conflicting_field_reduces_its_strength_and_retains_alternatives():
    profile = {"basis": "exact_public_email", "platform": "GitHub", "display_name": "Fixture",
               "location": "Example A", "fields": {"Headline": "Engineer"},
               "field_sources": {"fields.Headline": {"basis": "public_link", "source": "Public JSON-LD"}},
               "field_conflicts": {"location": [{"value": "Example A"}, {"value": "Example B"}]}}
    row = {"value": "Example A", "source": "GitHub", "basis": "exact_public_email"}
    report = annotate_report({"profiles": [profile], "identity": {"location": [row]}}, NOW)
    assert profile["confidence"]["score"] == 4
    assert profile["field_assessments"]["location"]["score"] == 1
    assert profile["field_assessments"]["fields.Headline"]["score"] == 2
    assert row["confidence"]["score"] == 1
    assert len(profile["field_conflicts"]["location"]) == 2


def test_identity_recency_propagates_without_treating_venue_as_residence():
    p = {"platform": "Google", "display_name": "Fixture", "basis": "provider_email", "last_seen": "2024"}
    row = {"value": "Fixture", "source": "Google", "basis": "provider_email"}
    location = {"value": "Example Cafe", "basis": "review_venue"}
    report = annotate_report({"profiles": [p], "identity": {"display_name": [row]}, "locations": [location]}, NOW)
    assert row["freshness"]["status"] == "potentially_outdated"
    assert location["freshness"]["status"] == "unknown"
    assert "not evidence of residence" in location["confidence"]["reason"]


def test_report_builder_assesses_registration_and_breach_without_mutating_source():
    data = {"github": {"status": "found", "username": "fixture", "url": "https://github.com/fixture", "created_at": "2000-01-01"},
            "breaches": {"sources": [{"name": "Example breach", "date": "2020"}]},
            "registration_checks": {"services": [{"service": "Example", "status": "found"}]}}
    report = build_email_evidence(data)
    assert report["profiles"][0]["confidence"]["score"] == 4
    assert report["profiles"][0]["freshness"]["status"] == "unknown"
    assert next(e for e in report["timeline"] if e["kind"] == "breach")["freshness"]["status"] == "historical"
    assert report["registrations"][0]["confidence"]["score"] == 1
    assert "confidence" not in data["registration_checks"]["services"][0]
