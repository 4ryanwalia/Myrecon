"""Photo collections survive enrichment and projection, and stay locked for guests."""
import pytest

from core import guest_reports
from services import email_public_profiles as service

ID = "100000000000000000001"
IMAGE = "https://lh3.googleusercontent.com/gps-cs/" + "B" * 40 + "=w400-h300-k-no"


def photo(**extra):
    return {"image_url": IMAGE, "name": "Example Viewpoint", "address": "Example Road", "date": "2020-01",
            "id": "fixture-photo", "source_url": f"https://www.google.com/maps/contrib/{ID}/photos", **extra}


def details(contributor):
    return {"status": "ok", "contributor_id": contributor, "reviews": [], "stats": {"Reviews": 0, "Ratings": 0, "Photos": 4},
            "photos": [photo(), photo(id="second", image_url="https://evil.example/x.jpg")],
            "photo_coverage": {"status": "partial", "returned": 2, "total_reported": 4},
            "limited": False, "source": "Google Maps public contributions", "reason": "", "display_name": "Example", "returned": 0, "limit": 100}


@pytest.fixture
def lookup(monkeypatch):
    monkeypatch.setenv("EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED", "true")
    monkeypatch.setenv("EMAIL_GOOGLE_REVIEWS_ENABLED", "false")
    identity = {"status": "found", "profiles": [{"platform": "Google", "url": f"https://www.google.com/maps/contrib/{ID}/reviews",
                "fields": {"ID": ID}, "stats": {"Photos": 4, "Answers": 2}, "display_name": "Example",
                "basis": "provider_email", "profile_status": "ok"}],
                "sources": [{"provider": "GHunt", "status": "found"}]}
    monkeypatch.setattr(service, "enrich_ghunt_email", lambda email: identity)
    monkeypatch.setattr("modules.email_maps_public.fetch_public_maps_reviews", details)
    return service.lookup_public_profiles("person@example.com")


def test_photos_reach_the_public_projection_and_bad_hosts_are_dropped(lookup):
    profile = lookup["profiles"][0]
    assert [p["id"] for p in profile["photos"]] == ["fixture-photo"]
    assert profile["photos"][0]["image_url"] == IMAGE
    assert profile["photo_coverage"]["status"] == "partial" and profile["photo_coverage"]["total_reported"] == 4
    assert profile["stats"]["Answers"] == 2
    assert "evil.example" not in str(lookup)


def test_projection_rejects_unexpected_photo_fields():
    row = {"platform": "Google", "url": f"https://www.google.com/maps/contrib/{ID}/reviews", "fields": {"ID": ID},
           "basis": "provider_email", "profile_status": "ok",
           "photos": [photo(latitude=1.5, uploader_email="private@example.com", date="yesterday")]}
    projected = service._profile(row)["photos"][0]
    assert "latitude" not in projected and "uploader_email" not in projected and "date" not in projected


def test_locked_deep_report_shows_photo_count_but_no_photo_content(lookup):
    report = guest_reports.deep({"status": "ok", "subject": "person@example.com", "mode": "email",
                                 "google_public_profiles": lookup}, complete=True)
    sections = {s["label"]: s["count"] for s in report["guest_access"]["sections"]}
    assert sections["Google Photos"] == 1
    text = str(report)
    assert "gps-cs" not in text and "Example Viewpoint" not in text and "fixture-photo" not in text
