"""Paid admission, streaming, and public-source evidence regression checks."""
import copy
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as api
import config
from core import plans, store
from core.firebase_auth import AuthError
from core.validation import ValidationError
from modules import deep_search_plan as plan, deep_search_sources as sources
from services import deep_search


@pytest.fixture
def client(monkeypatch):
    memory = store._MemoryStore()
    monkeypatch.setattr(plans, "store", memory)
    monkeypatch.setattr(store, "store", memory)
    monkeypatch.setattr(store, "persistent", lambda: True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    monkeypatch.setattr(api, "_full_slots", threading.BoundedSemaphore(1))
    def verify(token):
        if token != "valid":
            raise AuthError("Invalid token")
        return {"sub": "paid-user"}
    monkeypatch.setattr(api, "verify_id_token", verify)
    return api.create_app().test_client()


def post(client, token="valid", query="@octocat", **body):
    headers = {"Authorization": "Bearer " + token} if token is not None else {}
    return client.post("/api/investigate/stream", json={"query": query, **body}, headers=headers)


@pytest.mark.parametrize("token,status", [(None, 401), ("invalid", 401), ("valid", 402)])
def test_unpaid_calls_never_start_sources(client, monkeypatch, token, status):
    def forbidden(*args):
        pytest.fail("unpaid request reached sources")
    monkeypatch.setattr(deep_search, "search", forbidden)
    response = post(client, token, deep=True, deep_search_enabled=True, paid=True)
    assert response.status_code == status
    if status == 402:
        assert response.get_json()["scope"] == "deep_search"
        assert response.get_json()["account"]["deep_search_enabled"] is False
    assert plans.entitlements(plans.store.get("web/users/paid-user"))["standard_scans_left"] == 5


def test_paid_streams_partial_and_complete_without_spending_credits(client, monkeypatch):
    plans.grant_pass("paid-user", "extended", "paid-order")
    before = copy.deepcopy(plans.store.get("web/users/paid-user"))
    def fake(parsed, emit, stop):
        emit({"type": "partial", "data": {**parsed, "activity": [{"platform": "GitHub"}]}})
        return {"status": "ok", **parsed}
    monkeypatch.setattr(deep_search, "search", fake)
    response = post(client, query="Satya Nadella, Microsoft")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    events = [json.loads(line) for line in response.data.splitlines()]
    assert [e["type"] for e in events] == ["partial", "complete"]
    assert events[-1]["data"]["mode"] == "name"
    assert plans.store.get("web/users/paid-user") == before
    assert api._full_slots.acquire(blocking=False)
    api._full_slots.release()


def test_access_survives_spent_pack_and_legacy_expiry_is_enforced():
    assert plans.entitlements({"extended": {"scans_left": 0}})["deep_search_enabled"]
    assert plans.entitlements({"pro": {"plan": "weekly", "until": 101, "scans_left": 0}}, 100)["deep_search_enabled"]
    assert not plans.entitlements({"pro": {"plan": "weekly", "until": 99}}, 100)["deep_search_enabled"]


def test_spent_pack_can_run_and_busy_response_keeps_credits(client, monkeypatch):
    plans.store.set("web/users/paid-user", {"extended": {"scans_left": 0}})
    monkeypatch.setattr(deep_search, "search", lambda parsed, *args: {"status": "ok", **parsed})
    assert post(client).status_code == 200
    api._full_slots.acquire()
    try:
        assert post(client).get_json()["code"] == "scan_busy"
    finally:
        api._full_slots.release()
    assert plans.get_account("paid-user")["extended_scans_left"] == 0


def test_failed_pipeline_returns_safe_stream_error_and_releases_slot(client, monkeypatch):
    plans.grant_pass("paid-user", "extended", "paid-order")
    def fail(*args):
        raise RuntimeError("provider secret must not appear")
    monkeypatch.setattr(deep_search, "search", fail)
    response = post(client)
    assert b'"type": "error"' in response.data
    assert b"secret" not in response.data
    assert api._full_slots.acquire(blocking=False)
    api._full_slots.release()


def test_bad_input_cannot_reach_providers(client, monkeypatch):
    plans.grant_pass("paid-user", "extended", "paid-order")
    assert post(client, query='Name Person, x site:internal').status_code == 422
    assert post(client, query="http://127.0.0.1").status_code == 422
    assert client.options("/api/investigate/stream").status_code == 204


def test_input_mode_context_and_query_budget():
    assert plan.parse_input("@torvalds, Linux")["mode"] == "handle"
    parsed = plan.parse_input("Priya Sharma, Bangalore")
    assert parsed == {"subject": "Priya Sharma", "context": "Bangalore", "mode": "name"}
    names = plan.build_plan(**parsed)
    assert sum(q.get("scheduled", False) for q in names) == 16
    assert all('"Priya Sharma"' in q["text"] and q["text"].endswith(" Bangalore") for q in names)
    handles = plan.build_plan("nasa", "handle")
    assert sum(q.get("scheduled", False) for q in handles) == 18
    assert not any(q.get("scheduled") for q in handles if "picuki" in q["text"] or "imginn" in q["text"])
    assert not any(q["executed"] for q in handles)
    for value in ("", "@person name", "handle, x filetype:pdf", "a\nb", None):
        with pytest.raises(ValidationError):
            plan.parse_input(value)


def test_off_topic_results_and_handle_prefix_collisions_are_rejected():
    hit = {"url": "https://www.instagram.com/nasa/", "title": "NASA", "snippet": "Profile"}
    assert plan.accepts("site:instagram.com/nasa", hit)
    assert not plan.accepts("site:instagram.com/nasa", {**hit, "url": "https://www.instagram.com/nasa.fan/"})
    assert not plan.accepts('site:instagram.com "nasa"', {**hit, "url": "https://react.dev/", "title": "React tutorial"})
    assert not plan.accepts('"nasa"', {**hit, "url": "javascript:alert(1)"})
    assert not plan.accepts('"nasa"', {**hit, "url": "https://google.com/search?q=nasa"})
    assert not plan.accepts('"nasa"', {**hit, "url": "https://example.com/nasafan", "title": "nasafan"})
    assert plan.is_profile("https://reddit.com/user/nasa/comments", "nasa")
    assert not plan.is_profile("https://x.com/nasa/status/123", "nasa")


def test_activity_is_streamed_and_blocks_are_reported_as_unavailable(monkeypatch):
    account = {"platform": "GitHub", "handle": "nasa", "url": "https://github.com/nasa", "declared": [{"label": "Website", "url": "https://nasa.gov", "verified": False}], "posts": [], "activity_available": False}
    def blocked(_):
        raise sources.Unavailable()
    def absent(_):
        raise sources.Missing()
    monkeypatch.setattr(deep_search, "ACTIVITY_SOURCES", {"GitHub": lambda h: account, "Reddit": blocked, "DEV": absent})
    monkeypatch.setattr(deep_search, "keybase", absent)
    monkeypatch.setattr(deep_search, "run_plan", lambda *a: [])
    events = []
    result = deep_search.search(plan.parse_input("nasa"), events.append)
    assert result["activity"] == [account]
    assert result["partial"]
    checks = {x["source"]: x["state"] for x in result["source_checks"]}
    assert checks["Reddit"] == "unavailable" and checks["DEV"] == "not_found"
    assert result["owner_links"][0]["declared_on"] == "GitHub · nasa"
    assert any(e["type"] == "partial" and e["data"]["activity"] for e in events)


def test_name_search_never_calls_handle_sources_or_guesses_handles(monkeypatch):
    monkeypatch.setattr(deep_search, "NAME_SOURCES", {"Registry": lambda name: {"accounts": [{"detail": name, "candidate": True}]}})
    monkeypatch.setattr(deep_search, "run_plan", lambda *a: [])
    result = deep_search.search(plan.parse_input("Example Person"), lambda e: None)
    assert result["activity"] == []
    assert result["accounts"][0]["detail"] == "Example Person"


def test_github_keeps_confirmed_profile_when_feed_is_blocked(monkeypatch):
    monkeypatch.setattr(sources.PublicClient, "get", lambda self, *a, **k: {"login": "octocat", "blog": "https://github.blog", "bio": "Hello"})
    monkeypatch.setattr(sources.PublicClient, "optional", lambda *a, **k: (None, False))
    result = sources.github("octocat")
    assert result["platform"] == "GitHub" and not result["activity_available"]
    assert result["declared"][0]["url"] == "https://github.blog"
    with pytest.raises(sources.Unavailable):
        sources.github("somebodyelse")


def test_bluesky_reposts_do_not_become_authored_posts(monkeypatch):
    monkeypatch.setattr(sources.PublicClient, "get", lambda *a, **k: {"handle": "nasa.bsky.social", "did": "did:plc:nasa"})
    monkeypatch.setattr(sources.PublicClient, "optional", lambda *a, **k: ({"feed": [
        {"post": {"author": {"did": "did:plc:someone"}, "uri": "at://did:plc:someone/app.bsky.feed.post/1", "record": {"text": "Other person's words"}}},
        {"post": {"author": {"did": "did:plc:nasa"}, "uri": "at://did:plc:nasa/app.bsky.feed.post/2", "record": {"text": "Own words"}}},
    ]}, True))
    result = sources.bluesky("nasa")
    assert [p["text"] for p in result["posts"]] == ["Own words"]


def test_name_registry_search_requires_matching_profile_name(monkeypatch):
    def get(self, url, *args, **kwargs):
        if "search/users" in url:
            return {"items": [{"type": "User", "login": "unrelated"}]}
        return {"login": "unrelated", "name": "Other Person"}
    monkeypatch.setattr(sources.PublicClient, "get", get)
    assert sources.github_name("Example Person")["accounts"] == []
