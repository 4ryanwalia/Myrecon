import json

from core import guest_reports


def test_email_shows_one_actual_review_and_keeps_other_findings_server_side():
    report = {"status": "partial", "mode": "email", "subject": "owner@example.com",
              "google_public_profiles": {"status": "partial", "profiles": [{
                  "display_name": "Contributor name", "url": "https://www.google.com/maps/contrib/123/",
                  "reviews": [{"name": "Visible venue", "text": "Visible review text", "rating": 5,
                               "source_url": "https://www.google.com/maps/reviews/first",
                               "private_extra": "do not expose"},
                              {"name": "Hidden venue", "text": "Hidden review text"}],
                  "positions": [{"title": "Hidden job"}]}]}}
    partial = guest_reports.deep(report, complete=False)
    assert partial["guest_access"]["preview"] is None
    shown = guest_reports.deep(report, token=partial["guest_access"]["report_token"], complete=True)
    preview = shown["guest_access"]["preview"]
    assert preview["kind"] == "email_review"
    assert preview["data"]["text"] == "Visible review text"
    encoded = json.dumps(shown)
    assert "Hidden venue" not in encoded
    assert "Hidden review text" not in encoded
    assert "Hidden job" not in encoded
    assert "Contributor name" not in encoded
    assert "do not expose" not in encoded
    assert shown["guest_access"]["visible_count"] == 1
    assert guest_reports.read(shown["guest_access"]["report_token"])["data"] == report


def test_handle_preview_has_one_profile_without_nested_posts_or_other_profiles():
    shown = guest_reports.deep({"status": "ok", "mode": "handle", "subject": "example",
        "activity": [{"platform": "GitHub", "handle": "example", "url": "https://github.com/example",
                      "bio": "Visible bio", "posts": [{"text": "Hidden post"}]},
                     {"platform": "Reddit", "handle": "Hidden handle"}]}, complete=True)
    preview = shown["guest_access"]["preview"]
    assert preview["data"]["bio"] == "Visible bio"
    assert shown["guest_access"]["locked_count"] == 1
    assert "Hidden" not in json.dumps(shown)


def test_no_findings_does_not_invent_a_preview():
    shown = guest_reports.deep({"status": "unavailable", "mode": "email", "subject": "owner@example.com",
        "google_public_profiles": {"status": "unavailable", "profiles": []}}, complete=True)
    assert shown["guest_access"]["preview"] is None
    assert shown["guest_access"]["visible_count"] == 0
