"""Account-route parsing, evidence boundaries and explicit follow security."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import netguard
from core.validation import ValidationError
from modules import profile_connections as links


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(netguard, "_addresses_for", lambda host: ["8.8.8.8"])


@pytest.mark.parametrize("url,platform,handle", [
    ("https://www.github.com/Other?utm_source=bio#about", "GitHub", "Other"),
    ("https://reddit.com/u/other/", "Reddit", "other"),
    ("https://news.ycombinator.com/user?id=other", "Hacker News", "other"),
    ("https://other.tumblr.com/", "Tumblr", "other"),
    ("https://www.linkedin.com/in/other", "LinkedIn", "other"),
    ("https://www.tiktok.com/@other", "TikTok", "other"),
    ("https://bsky.app/profile/other.bsky.social", "Bluesky", "other.bsky.social"),
    ("https://bsky.app/profile/person.example.com", "Bluesky", "person.example.com"),
])
def test_catalogue_account_routes(url, platform, handle):
    profile = links.account_url(url)
    assert profile["platform"] == platform and profile["handle"] == handle
    assert links.account_url(profile["url"]) == profile


@pytest.mark.parametrize("url", [
    "https://example.com/other", "https://github.com/other/repo", "https://x.com/other/status/1",
    "https://github.com.evil.test/other", "https://x.com/intent", "https://instagram.com/explore/",
    "https://user:pass@github.com/other", "https://github.com:8080/other",
    "https://github.com/other%2frepo", "https://github.com/%252fother", "file:///other",
    "https://github.com/person@example.com", "https://127.0.0.1/other",
    "https://instagram.com/p", "https://github.com/marketplace", "https://facebook.com/watch",
])
def test_posts_arbitrary_urls_and_unsafe_inputs_are_not_accounts(url):
    assert links.account_url(url) is None


def test_supported_destination_with_private_dns_is_rejected(monkeypatch):
    monkeypatch.setattr(netguard, "_addresses_for", lambda host: ["169.254.169.254"])
    assert links.account_url("https://github.com/other") is None


def result(declared):
    return {"subject": "original", "mode": "handle", "activity": [{"platform": "GitHub", "handle": "original",
            "url": "https://github.com/original", "source": "GitHub public API", "declared": declared},
            {"platform": "Reddit", "handle": "original", "url": "https://reddit.com/user/original", "source": "Reddit public JSON"}]}


def test_evidence_deduplication_and_source_attribution():
    rows = links.connections(result([
        {"url": "https://x.com/different", "verified": True},
        {"url": "https://www.x.com/different/?utm_source=bio"},
        {"url": "https://github.com/original"},
        {"url": "https://github.com/different", "verification": {"provider": "Mastodon", "verified_at": "2026-10-05T00:00:00Z"}},
    ]))
    assert [r["evidence_type"] for r in rows] == ["same_username", "profile_link", "platform_verified"]
    assert rows[1]["verification"] is None
    assert rows[1]["source"]["url"] == "https://github.com/original"
    assert rows[1]["destination"]["handle"] == "different"
    assert not rows[0]["can_follow"]
    assert rows[0]["source"]["url"] == "https://github.com/original"
    assert rows[0]["destination"]["url"] == "https://reddit.com/user/original"


def test_suggestions_are_capped_without_fetching_destinations():
    rows = links.connections(result([{"url": f"https://github.com/person{i}"} for i in range(200)]))
    assert len(rows) == links.MAX_SUGGESTIONS


def test_follow_tokens_bind_user_evidence_and_trail():
    data = result([{"url": "https://github.com/different"}])
    data["connections"] = links.connections(data)
    action = links.attach_actions(data, "user1")["connections"][1]["action"]
    assert action["requires_user_action"] and action["endpoint"] == "/api/investigate/stream"
    token = action["body"]["follow_token"]
    parsed = links.parse_follow(token, "user1")
    assert parsed["subject"] == "different"
    assert parsed["connection_trail"][0]["evidence_type"] == "profile_link"
    assert parsed["connection_trail"][0]["source"]["handle"] == "original"
    for invalid, user in [(token + "tampered", "user1"), (token, "user2")]:
        with pytest.raises(ValidationError):
            links.parse_follow(invalid, user)


def test_cycles_depth_and_dns_revalidation(monkeypatch):
    edge = {"source": {"platform": "GitHub", "handle": "original", "url": "https://github.com/original"},
            "destination": {"platform": "GitHub", "handle": "different", "url": "https://github.com/different"}}
    data = result([{"url": "https://github.com/different"}, {"url": "https://x.com/new"}])
    data["connection_trail"] = [edge]
    rows = links.connections(data)
    assert not next(r for r in rows if r["destination"]["handle"] == "different")["can_follow"]
    data["connection_trail"] *= links.MAX_FOLLOWS
    assert not any(r["can_follow"] for r in links.connections(data))
    token = links._signer().dumps({"uid": "u", "trail": [edge]})
    monkeypatch.setattr(netguard, "_addresses_for", lambda host: ["127.0.0.1"])
    with pytest.raises(ValidationError):
        links.parse_follow(token, "u")


def test_keybase_requires_successful_proof_state():
    data = {"subject": "original", "mode": "handle", "identity": {"username": "original", "url": "https://keybase.io/original", "source": "Keybase published proofs", "proofs": [
        {"url": "https://github.com/claim", "verification": {"provider": "Keybase", "proof_url": "https://github.com/claim/proof"}},
        {"url": "https://github.com/proven", "verification": {"provider": "Keybase", "state": 1, "proof_url": "https://github.com/proven/proof"}},
    ]}}
    assert [r["evidence_type"] for r in links.connections(data)] == ["profile_link", "platform_verified"]
