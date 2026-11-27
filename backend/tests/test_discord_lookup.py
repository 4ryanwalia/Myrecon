import app as appmod
from services import discord_lookup

USER_ID = "175928847299117063"


class Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


def _client():
    return appmod.create_app().test_client()


def test_not_configured_without_token(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    called = []
    monkeypatch.setattr(discord_lookup.requests, "get", lambda *a, **k: called.append(1))
    body = _client().get(f"/api/discord/user/{USER_ID}").get_json()
    assert body["state"] == "not_configured"
    assert called == []


def test_found_projects_public_fields_only(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    seen = {}

    def fake_get(url, headers, timeout):
        seen["url"], seen["headers"] = url, headers
        return Response(200, {
            "id": USER_ID, "username": "fixture", "global_name": "Fixture",
            "avatar": "a_abc", "banner": "def", "accent_color": 0x5865F2,
            "public_flags": (1 << 0) | (1 << 7) | (1 << 22), "email": "never@example.com",
        })

    monkeypatch.setattr(discord_lookup.requests, "get", fake_get)
    result = discord_lookup.lookup_user(USER_ID)
    assert seen["url"].endswith(f"/users/{USER_ID}")
    assert seen["headers"]["Authorization"] == "Bot test-token"
    assert seen["headers"]["User-Agent"].startswith("DiscordBot (")
    assert result["username"] == "fixture"
    assert result["avatar_url"].endswith(f"/avatars/{USER_ID}/a_abc.gif?size=256")
    assert result["banner_url"].endswith(f"/banners/{USER_ID}/def.png?size=256")
    assert result["accent_color"] == "#5865f2"
    # Undocumented bits are dropped rather than guessed at.
    assert result["badges"] == ["Discord Employee", "House Brilliance Member"]
    assert "email" not in result


def test_unknown_user_and_errors(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setattr(discord_lookup.requests, "get", lambda *a, **k: Response(404, {"code": 10013}))
    assert discord_lookup.lookup_user(USER_ID) == {"state": "not_found"}
    monkeypatch.setattr(discord_lookup.requests, "get", lambda *a, **k: Response(429, {"retry_after": 2.4}))
    limited = discord_lookup.lookup_user(USER_ID)
    assert limited["state"] == "rate_limited" and limited["retry_after"] == 3
    assert limited["status"] == "error"  # so app.cached() never stores it
    monkeypatch.setattr(discord_lookup.requests, "get", lambda *a, **k: Response(500))
    assert discord_lookup.lookup_user(USER_ID)["state"] == "unavailable"


def test_route_rejects_non_ids(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    client = _client()
    assert client.get("/api/discord/user/abc").status_code == 422
    assert client.get("/api/discord/user/99999999999999999999").status_code == 422
    assert client.get("/api/discord/user/123").status_code == 422
