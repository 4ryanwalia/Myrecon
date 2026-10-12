"""Offline evidence contracts, request budgets and website report boundaries."""
import json
from unittest.mock import MagicMock

import pytest

from modules.username_integrations import PLATFORMS, append_missing, parse_account
from modules.sweep import CATALOGUE, EXTENDED, Sweep
import services.search as search


def next_page(props, page="/user/[...username]"):
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"page": page, "props": {"pageProps": props}}) + '</script>'


def examples(handle="alice"):
    return {
        "daily.dev": next_page({"user": {"id": "id1", "username": handle, "name": "Alice", "bio": "Developer", "image": "https://cdn.example/a.png", "reputation": 3}, "userStats": {"numFollowers": 0, "numFollowing": 2}}),
        "Modrinth": json.dumps({"id": "id1", "username": handle, "name": "Alice", "bio": "Mods", "avatar_url": "https://cdn.example/a.png"}),
        "stats.fm": json.dumps({"item": {"id": "id1", "customId": handle, "displayName": "Alice", "image": "https://cdn.example/a.png"}}),
        "Warpcast": json.dumps({"result": {"user": {"fid": 123, "username": handle, "displayName": "Alice", "pfp": {"url": "https://cdn.example/a.png"}, "profile": {"bio": {"text": "Hello"}}, "followerCount": 0, "followingCount": 2}}}),
        "Character.AI": json.dumps({"result": {"data": {"json": {"username": handle, "name": "Alice", "bio": "Characters", "avatar_file_name": "a.png", "num_followers": 0, "num_following": 2, "characters": []}}}}),
        "Inkitt": 'globalData.user = ' + json.dumps({"id": 123, "username": handle, "name": "Alice", "description": "Writer", "followers_count": 0, "published_stories_count": 3, "homepage_url": "https://example.com", "large_profile_picture_url": "https://cdn.example/a.png"}) + ';',
        "Payhip": 'window.payhipShop = ' + json.dumps({"user": {"username": handle, "shopName": "Alice", "bio": '<b>Maker</b><a href="https://example.com">Site</a>', "websiteUrl": "javascript:alert(1)", "resizedLogo": {"original": {"src": "https://cdn.example/a.png"}}}}) + ';',
        "Luma": next_page({"initialData": {"user": {"api_id": "usr1", "username": handle, "name": "Alice", "bio_short": "Host", "avatar_url": "https://cdn.example/a.png", "website": "https://example.com"}, "event_hosted_count": 0, "event_attended_count": 2}}),
        "Bio Site": 'window.initial_state=' + json.dumps({"metadata": {"handle": handle}, "header": {"name": "Alice", "bio": "Creator", "profilePhoto": "https://cdn.example/a.png"}}) + '; window.additional={};',
    }


NAMES = [p["name"] for p in PLATFORMS]


@pytest.mark.parametrize("name", NAMES)
def test_only_exact_account_objects_are_found_and_metadata_is_preserved(name):
    verdict, details = parse_account(name, 200, examples()[name], "alice")
    assert verdict == "found"
    assert details["display_name"] == "Alice"
    assert details["profile_pic_url"].startswith("https://")
    assert parse_account(name, 200, examples("bob")[name], "alice")[0] == "unknown"
    if name == "Payhip":
        assert details["public_links"] == ["https://example.com"]
        assert "<b>" not in details["bio"]
    if name == "Inkitt":
        assert details["statistics"]["followers"] == 0
        assert details["statistics"]["stories"] == 3


@pytest.mark.parametrize("name", NAMES)
def test_distinguishable_missing_account_response(name):
    code, body = 404, "not found"
    if name == "Inkitt":
        body = 'globalData.user = {}; controller: "errors"; action: "not_found"'
    elif name == "Payhip":
        body = '<title>404 Page Not Found</title>The page you requested was not found.'
    elif name == "Luma":
        code, body = 200, next_page({"status": 404, "initialData": None})
    elif name == "Character.AI":
        code, body = 500, json.dumps({"error": {"json": {"data": {"path": "social.publicProfile", "axiosErrorData": {"upstreamStatus": 404}}}}})
    assert parse_account(name, code, body, "alice") == ("not_found", {})


def response(code, body):
    resp = MagicMock(status_code=code, encoding="utf-8")
    resp.__enter__.return_value = resp
    resp.iter_content.return_value = iter([body.encode()])
    return resp


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("code,body", [(200, '{}'), (200, '<title>alice</title>'), (200, '[]'),
    (200, 'null'), (200, '<html>Just a moment</html>'), (200, 'Sign in to continue'),
    (403, '{}'), (429, '{}'), (302, '{}'), (500, '{}')])
def test_uncertainty_never_falls_back_or_becomes_a_hit_or_absence(name, code, body):
    sweep = Sweep("alice")
    sweep.session.get = MagicMock(return_value=response(code, body))
    result = sweep.probe(next(p for p in PLATFORMS if p["name"] == name))
    assert result["verdict"] == "unknown"
    assert "metadata_source" not in result
    assert sweep.session.get.call_count == 1
    assert sweep.session.get.call_args.kwargs["allow_redirects"] is False
    sweep.session.close()


@pytest.mark.parametrize("name", NAMES)
def test_adapter_uses_one_request_and_existing_result_shape(name):
    sweep = Sweep("alice")
    sweep.session.get = MagicMock(return_value=response(200, examples()[name]))
    result = sweep.probe(next(p for p in PLATFORMS if p["name"] == name))
    assert result["verdict"] == "found"
    assert result["source"] == "username_sweep"
    assert result["metadata_source"]["platform"] == name
    assert result["metadata_complete"]
    sweep.session.get.assert_called_once()
    live = search._live_view(result, "alice")
    for key in ("display_name", "bio", "profile_pic_url", "statistics", "public_links", "metadata_source"):
        if key in result:
            assert live[key] == result[key]
    assert "status_code" not in live
    sweep.session.close()


def test_duplicate_domains_and_api_namespaces_are_suppressed():
    base = [{"name": "Different filename", "url": "https://www.payhip.com/{username}"}]
    extra = [{"name": "Another label", "url": "https://other.example/u/{username}", "api": "https://api.modrinth.com/v2/user/{username}"}]
    names = [p["name"] for p in append_missing(base, extra)]
    assert "Payhip" not in names and "Modrinth" not in names
    assert all(sum(p["name"] == name for p in EXTENDED) == 1 for name in NAMES)
    assert not any(p.get("integration") for p in CATALOGUE[:100])
    assert all(p in EXTENDED for p in PLATFORMS)


def test_enrichment_does_not_refetch_or_overwrite_adapter_metadata(monkeypatch):
    enricher = MagicMock()
    monkeypatch.setattr(search, "ProfileEnricher", enricher)
    search._enrich_profiles([{"exists": True, "platform": "Modrinth", "metadata_complete": True}])
    enricher.assert_not_called()


@pytest.mark.parametrize("identity", [True, {}, ["id"], -1])
def test_malformed_identity_cannot_confirm_an_account(identity):
    body = json.dumps({"id": identity, "username": "alice"})
    assert parse_account("Modrinth", 200, body, "alice") == ("unknown", {})


def test_invalid_farcaster_handle_makes_no_request():
    sweep = Sweep("too-long-farcaster-name")
    sweep.session.get = MagicMock()
    hit = sweep.probe(next(p for p in PLATFORMS if p["name"] == "Warpcast"))
    assert hit["verdict"] == "unknown" and hit["reason_code"] == "invalid_handle"
    sweep.session.get.assert_not_called()
    sweep.session.close()


def test_oversized_and_interrupted_bodies_are_not_partial_account_evidence():
    p = next(p for p in PLATFORMS if p["name"] == "Modrinth")
    sweep = Sweep("alice")
    resp = response(200, examples()["Modrinth"] + " " * 1_000_000)
    sweep.session.get = MagicMock(return_value=resp)
    assert sweep.probe(p)["verdict"] == "unknown"
    def interrupted():
        yield examples()["Modrinth"].encode()
        raise OSError("interrupted stream")
    resp.iter_content.return_value = interrupted()
    assert sweep.probe(p)["verdict"] == "unknown"
    sweep.session.close()


def test_new_hits_stream_before_complete_with_public_metadata(monkeypatch):
    import modules.sweep as module
    platform = next(p for p in PLATFORMS if p["name"] == "Inkitt")
    def probe(self, p):
        if p != platform:
            return self._hit(p, "not_found", p["url"], 404, "none", "status_absent")
        hit = self._hit(p, "found", "https://www.inkitt.com/alice", 200, "high", "api_user")
        hit.update(parse_account("Inkitt", 200, examples()["Inkitt"], "alice")[1])
        hit["metadata_complete"] = True
        hit["metadata_source"] = {"platform": "Inkitt", "url": hit["url"], "basis": "public account object"}
        return hit
    monkeypatch.setattr(module.Sweep, "probe", probe)
    monkeypatch.setattr(search, "_code_exposure", lambda *a: [])
    monkeypatch.setattr(search.IdentityCorrelator, "correlate", lambda *a, **k: [])
    events = list(search.stream_username("alice", scope="full"))
    hit = next(e for e in events if e["type"] == "found")
    assert events.index(hit) < len(events) - 1
    complete = events[-1]["data"]
    assert complete["results"]["profiles"][0]["public_links"] == ["https://example.com"]
    assert len(complete["platform_checks"]) == len(CATALOGUE)
