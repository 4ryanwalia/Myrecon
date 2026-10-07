"""Offline checks of identity attribution, date meaning and optional enrichment."""
import pytest

from modules.email_evidence import build_email_evidence, event_date
from modules.email_lookup import EmailLookup


@pytest.mark.parametrize("value", ["", "2 years ago", "2025-02-30", "2025-13", "9999", "2025-1-01", "2025-02-03Tbad", "2025-02-03T00:00:00"])
def test_unknown_invalid_and_future_dates_are_not_invented(value):
    assert event_date(value) is None


def test_date_precision_and_utc_day_are_preserved():
    assert event_date("2020")["date_label"] == "2020"
    assert event_date("2020-03")["precision"] == "month"
    assert event_date("2020-03-01T00:30:00+02:00")["date"] == "2020-02-29"


def test_summary_keeps_attribution_deduplicates_breaches_and_never_guesses_identity():
    data = {"query": {"email": "guess.name@example.com"},
            "github": {"username": "dev", "status": "found", "display_name": "Example Dev", "location": "Declared place", "evidence_url": "https://github.com/dev/repo/commit/1", "created_at": "2020-04-01T00:00:00Z", "commit_date": "2021-05-01T00:00:00Z"},
            "breaches": {"sources": [{"name": "Canva.com", "date": "2019"}, {"name": "Unknown"}]},
            "darkweb": {"breaches": [{"name": "Canva", "date": "2019"}]},
            "registration_checks": {"services": [{"service": "Spotify", "domain": "spotify.com", "status": "found"}, {"service": "Spotify", "domain": "spotify.com", "status": "found"}, {"service": "Other", "status": "timeout"}]}}
    report = build_email_evidence(data)
    assert report["counts"]["named_breaches"] == 2
    assert report["counts"]["registration_signals"] == 1
    assert len(report["timeline"]) == 3
    assert report["earliest"]["date"] == "2019"
    assert report["latest"]["title"] == "Public GitHub commit"
    assert report["identity"]["display_name"][0]["basis"] == "historical_commit"
    assert report["timeline"][-1]["sources"] == ["XposedOrNot analytics", "LeakCheck"]
    assert len(report["undated_events"]) == 1
    assert "guess.name" not in str(report)
    assert "first seen" in report["breach_date_note"]


def test_conflicting_dates_remain_separate_and_no_dates_means_no_range():
    report = build_email_evidence({"breaches": {"sources": [{"name": "Canva", "date": "2019"}]}, "darkweb": {"breaches": [{"name": "Canva", "date": "2020"}]}})
    assert len(report["timeline"]) == 2
    assert report["counts"]["named_breaches"] == 1
    assert report["timeline"][0]["sources"] == ["XposedOrNot analytics"]
    assert report["timeline"][1]["sources"] == ["LeakCheck"]
    assert all(e["date_conflict"] for e in report["timeline"])
    empty = build_email_evidence({"query": {"email": "name@example.com"}})
    assert empty["earliest"] is None
    assert empty["identity"]["display_name"] == []


def test_duplicate_breach_names_merge_year_and_month_dates_with_all_source_evidence():
    report = build_email_evidence({
        "darkweb": {"breaches": [{"name": "BigBasket", "date": "2020"},
                                   {"name": "GamingMonk", "date": "2020"},
                                   {"name": "Canva", "date": "2019"}]},
        "breaches": {"sources": [{"name": "BigBasket.com", "date": "2020-12"},
                                  {"name": "GamingMonk", "date": "2020-12"},
                                  {"name": "Canva.com", "date": "2019-05"}]}})
    assert len(report["timeline"]) == 3
    assert report["counts"]["named_breaches"] == 3
    for event in report["timeline"]:
        assert event["precision"] == "month"
        assert event["sources"] == ["XposedOrNot analytics", "LeakCheck"]
        assert [e["precision"] for e in event["date_evidence"]] == ["year", "month"]
        assert event["date_evidence"][0]["sources"] == ["XposedOrNot analytics"]
        assert event["date_evidence"][1]["sources"] == ["LeakCheck"]
        assert event["date_conflict"] is False


def test_breach_precision_can_merge_to_reported_day_without_inventing_first_seen():
    report = build_email_evidence({
        "darkweb": {"breaches": [{"name": "Example", "date": "2019"}]},
        "breaches": {"sources": [{"name": "Example.com", "date": "2019-05"}]},
        "breach_details": {"records": [{"name": "Example", "date": "2019-05-24"}]}})
    assert len(report["timeline"]) == 1
    event = report["timeline"][0]
    assert event["date"] == "2019-05-24"
    assert event["precision"] == "day"
    assert event["date_evidence"][-1]["sources"] == ["LeakCheck Pro"]
    assert len(event["date_evidence"]) == 3
    assert event["sources"] == ["XposedOrNot analytics", "LeakCheck", "LeakCheck Pro"]
    assert report["earliest"] == report["latest"] == event
    assert "first seen" in report["breach_date_note"]


def test_coarse_date_does_not_hide_conflicting_months():
    report = build_email_evidence({
        "darkweb": {"breaches": [{"name": "Example", "date": "2019"}]},
        "breaches": {"sources": [{"name": "Example", "date": "2019-04"}]},
        "breach_details": {"records": [{"name": "Example", "date": "2019-05"}]}})
    assert [e["date"] for e in report["timeline"]] == ["2019-05", "2019-04"]
    assert all(e["date_conflict"] for e in report["timeline"])
    assert all(e["date_evidence"][0]["date"] == "2019" for e in report["timeline"])
    assert report["timeline"][0]["sources"] == ["XposedOrNot analytics", "LeakCheck Pro"]
    assert report["timeline"][1]["sources"] == ["XposedOrNot analytics", "LeakCheck"]


def test_same_precision_conflict_is_not_hidden_by_a_shared_month():
    report = build_email_evidence({
        "darkweb": {"breaches": [{"name": "Example", "date": "2019-05"}]},
        "breaches": {"sources": [{"name": "Example", "date": "2019-05-12"},
                                  {"name": "Example", "date": "2019-05-24"}]}})
    assert [e["date"] for e in report["timeline"]] == ["2019-05-24", "2019-05-12"]
    assert all(e["date_conflict"] for e in report["timeline"])
    assert all([d["precision"] for d in e["date_evidence"]] == ["month", "day"] for e in report["timeline"])


@pytest.mark.parametrize("coarse_provider", ["darkweb", "breaches"])
def test_precision_merging_does_not_depend_on_provider_order(coarse_provider):
    data = {"darkweb": {"breaches": [{"name": "Example", "date": "2019" if coarse_provider == "darkweb" else "2019-05"}]},
            "breaches": {"sources": [{"name": "Example", "date": "2019" if coarse_provider == "breaches" else "2019-05"}]}}
    report = build_email_evidence(data)
    assert len(report["timeline"]) == 1
    assert report["timeline"][0]["date"] == "2019-05"
    assert len(report["timeline"][0]["sources"]) == 2


def public_profile(platform="LinkedIn", **values):
    return {"platform": platform, "url": "", "username": "", "display_name": "", "source": "Example provider",
            "basis": "provider_email", "fields": {}, "stats": {}, "lists": {}, **values}


def test_canonical_profile_urls_merge_aliases_tracking_and_richer_fields_without_changing_basis():
    from copy import deepcopy
    data = {"github": {"username": "dev", "status": "found", "url": "https://github.com/dev",
                       "bio": "Short summary", "stats": {"Public repositories": 0}, "fields": {"ID": 17},
                       "evidence_url": "https://github.com/dev/repo/commit/1", "created_at": "2020-01-01T00:00:00Z"},
            "profile_enrichment": {"profiles": [public_profile(
                "github.com", username="DEV", url="https://www.github.com/dev/?utm_source=example&trk=profile#about",
                bio="A longer public summary with extra source detail", fields={"ID": "17", "Email verified": "Yes"},
                stats={"Followers": 4}, lists={"Auth methods": ["email"]}, created_at="2020-01-01")]}}
    original = deepcopy(data)
    report = build_email_evidence(data)
    assert data == original
    assert len(report["profiles"]) == 1
    profile = report["profiles"][0]
    assert profile["platform"] == "GitHub"
    assert profile["basis"] == "historical_commit"
    assert profile["source"] == "GitHub public API"
    assert profile["stats"] == {"Public repositories": 0, "Followers": 4}
    assert profile["fields"]["Email verified"] == "Yes"
    assert profile["bio"].startswith("A longer")
    assert profile["sources"] == ["GitHub public API", "Example provider"]
    assert [p["basis"] for p in profile["provenance"]] == ["historical_commit", "provider_email"]
    assert [p["value"] for p in profile["field_conflicts"]["bio"]] == ["Short summary", "A longer public summary with extra source detail"]
    assert profile["field_sources"]["stats.Followers"]["source"] == "Example provider"
    assert "fields.ID" not in profile["field_conflicts"]
    assert "url" not in profile["field_conflicts"]
    assert len(report["timeline"]) == 1
    assert report["timeline"][0]["sources"] == ["GitHub public API", "Example provider"]
    assert len(report["timeline"][0]["source_evidence"]) == 2


def test_canonical_url_match_works_without_matching_usernames_or_ids():
    report = build_email_evidence({"profile_enrichment": {"profiles": [
        public_profile(url="https://linkedin.com/in/example"),
        public_profile("linkedin.com", url="https://www.linkedin.com/in/example/?utm_medium=test&trk=email", display_name="Example")
    ]}})
    assert len(report["profiles"]) == 1
    assert report["profiles"][0]["display_name"] == "Example"


def test_twitter_x_aliases_and_case_insensitive_handles_share_one_profile():
    report = build_email_evidence({"profile_enrichment": {"profiles": [
        public_profile("Twitter", url="https://www.twitter.com/ExampleUser/", username="ExampleUser"),
        public_profile("X", url="https://x.com/exampleuser?utm_source=test", username="exampleuser")
    ]}})
    assert len(report["profiles"]) == 1
    assert report["profiles"][0]["platform"] == "X"


def test_id_and_query_identifier_conflicts_preserve_distinct_accounts():
    report = build_email_evidence({"profile_enrichment": {"profiles": [
        public_profile("Google", fields={"ID": "one"}, url="https://google.com/profile/example", username="same"),
        public_profile("Google Maps", fields={"ID": "two"}, url="https://google.com/profile/example", username="same"),
        public_profile("Facebook", url="https://facebook.com/profile.php?id=1", username="same"),
        public_profile("Facebook", url="https://www.facebook.com/profile.php?id=2&utm_source=test", username="same")
    ]}})
    assert len(report["profiles"]) == 4


def test_shared_name_homepage_or_avatar_never_merges_profiles():
    report = build_email_evidence({"profile_enrichment": {"profiles": [
        public_profile("Google", display_name="Example", avatar_url="https://images.example/avatar.png", url="https://google.com/"),
        public_profile("Google", display_name="Example", avatar_url="https://images.example/avatar.png", url="https://www.google.com/")
    ]}})
    assert len(report["profiles"]) == 2


def test_same_handle_with_distinct_profile_urls_is_not_silently_merged():
    report = build_email_evidence({"profile_enrichment": {"profiles": [
        public_profile("LinkedIn", username="same", url="https://linkedin.com/in/first"),
        public_profile("LinkedIn", username="same", url="https://linkedin.com/in/second")
    ]}})
    assert len(report["profiles"]) == 2


def test_ambiguous_profile_match_does_not_choose_between_distinct_account_ids():
    report = build_email_evidence({"profile_enrichment": {"profiles": [
        public_profile("LinkedIn", username="same", url="https://linkedin.com/in/example", fields={"ID": "one"}),
        public_profile("LinkedIn", username="same", url="https://linkedin.com/in/example", fields={"ID": "two"}),
        public_profile("LinkedIn", username="same", url="https://linkedin.com/in/example")
    ]}})
    assert len(report["profiles"]) == 3
    assert [p["fields"].get("ID") for p in report["profiles"]] == ["one", "two", None]


def test_matching_stable_id_merges_profile_aliases_and_complementary_collections():
    first = public_profile("Google", fields={"ID": "123"}, stats={"Reviews": 0}, lists={"Active Google apps": ["Maps"]},
                           reviews=[{"name": "Example cafe", "address": "Public venue", "date": "2020-01-02", "text": "Good"}])
    second = public_profile("Google Maps", fields={"ID": "123", "Enterprise user": "No"}, stats={"Answers": 3},
                            lists={"Active Google apps": ["Maps", "Photos"]}, reviews=[
                                {"name": "Example cafe", "address": "Public venue", "date": "2020-01-02", "text": "Good", "owner_reply": "Thank you", "latitude": 0, "longitude": 0},
                                {"name": "Example cafe", "address": "Public venue", "date": "2021-01-02", "text": "Good"}])
    report = build_email_evidence({"profile_enrichment": {"profiles": [first, second]}})
    assert len(report["profiles"]) == 1
    profile = report["profiles"][0]
    assert profile["stats"] == {"Reviews": 0, "Answers": 3}
    assert profile["lists"]["Active Google apps"] == ["Maps", "Photos"]
    assert len(profile["reviews"]) == 2
    assert profile["reviews"][0]["owner_reply"] == "Thank you"
    assert profile["reviews"][0]["latitude"] == 0
    assert len(report["timeline"]) == 2
    assert len(report["locations"]) == 2


def test_career_collection_merge_keeps_richer_rows_and_distinct_positions_degrees():
    first = public_profile(url="https://linkedin.com/in/example", positions=[
        {"company": "Example Co", "title": "Engineer", "start": "2020-01"}], education=[
            {"school": "Example University", "degree": "BSc", "start": "2016"}])
    second = public_profile(url="https://www.linkedin.com/in/example/", positions=[
        {"company": "Example Co", "title": "Engineer", "start": "2020-01", "current": False, "description": "Public role"},
        {"company": "Example Co", "title": "Engineer", "start": "2022-01"}], education=[
            {"school": "Example University", "degree": "BSc", "start": "2016", "end": "2020"},
            {"school": "Example University", "degree": "MSc", "start": "2021"}])
    profile = build_email_evidence({"profile_enrichment": {"profiles": [first, second]}})["profiles"][0]
    assert len(profile["positions"]) == 2
    assert profile["positions"][0]["current"] is False
    assert profile["positions"][0]["description"] == "Public role"
    assert len(profile["education"]) == 2
    assert profile["education"][0]["end"] == "2020"


def test_service_adds_evidence_without_changing_opt_in(monkeypatch):
    from services import email as service
    choices = []
    monkeypatch.setattr(EmailLookup, "scan", lambda self, email, check_linked_accounts: choices.append(check_linked_accounts) or {"query": {"email": email}, "account_checks": {"enabled": check_linked_accounts}})
    result = service.scan_email("fixture@example.com", check_linked_accounts=False)
    assert choices == [False]
    assert result["status"] == "ok"
    assert result["evidence_report"]["profiles"] == []
    assert result["evidence_report"]["earliest"] is None


def test_owner_declared_links_are_not_independently_verified_profiles():
    from modules.email_lookup import _linked_services
    result = _linked_services({"exists": True, "accounts": [{"name": "LinkedIn", "url": "https://linkedin.com/in/example"}, {"name": "!!!"}]}, {}, {}, {}, {}, {})
    linkedin = next(r for r in result["services"] if r["service"] == "LinkedIn")
    assert linkedin["basis"] == "owner_declared"


class Response:
    def __init__(self, data=None, status=200):
        self.data, self.status_code = data, status
    def json(self):
        return self.data


@pytest.mark.parametrize("profile_status", [200, 429, 503])
def test_commit_evidence_survives_enrichment_failure(monkeypatch, profile_status):
    email = "fixture@example.com"
    responses = iter([Response({"items": []}), Response({"items": [{"author": {"login": "dev"}, "commit": {"author": {"email": email, "date": "2020-01-01T00:00:00Z"}}, "html_url": "https://github.com/dev/repo/commit/1"}]}),
                      Response({"login": "dev", "name": "Dev", "public_repos": 0, "followers": 2, "created_at": "2019-01-01T00:00:00Z", "private_gists": 20, "password": "must-not-forward"}, profile_status)])
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **kw: next(responses))
    found = EmailLookup().github(email)
    assert found["status"] == "found"
    assert found["commit_date"] == "2020-01-01T00:00:00Z"
    assert "password" not in found and "private_gists" not in found
    if profile_status == 200:
        assert found["stats"]["Public repositories"] == 0
    else:
        assert found["profile_status"] != "ok"
