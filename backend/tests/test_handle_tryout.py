from urllib.parse import urlsplit

import pytest

import app
import config
from services import handle_tryout as tryout


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    return app.app.test_client()


def test_catalog_counts_distinct_public_services(client):
    data = client.get("/api/handle-tryout/platforms").get_json()
    platforms = [p["name"] for p in data["platforms"]]
    hosts = {urlsplit(tryout.PLATFORMS[n]["url"]).hostname.removeprefix("www.") for n in platforms}
    assert len(platforms) == len(hosts) >= 500
    assert set(data["popular"]) <= set(platforms)
    assert {"YouTube", "TikTok", "Instagram", "GitHub", "Hacker News"} <= set(data["popular"])
    assert data["batchSize"] == tryout.BATCH_SIZE


@pytest.mark.parametrize("body", [
    ["GitHub"], {"handle": "../x", "platforms": ["GitHub"]},
    {"handle": "orbit", "platforms": ["https://example.org"]},
    {"handle": "orbit", "platforms": ["GitHub", "GitHub"]},
    {"handle": "orbit", "platforms": list(tryout.PLATFORMS)[:tryout.BATCH_SIZE + 1]},
    {"handle": "orbit", "platforms": []},
])
def test_invalid_request_never_starts_checks(client, monkeypatch, body):
    monkeypatch.setattr(tryout, "check_batch", lambda *_: pytest.fail("unexpected check"))
    assert client.post("/api/handle-tryout/check", json=body).status_code == 422


def test_requested_platforms_only_and_honest_outcomes(client, monkeypatch):
    names = ["GitHub", "Dev.to", "Twitch", "YouTube", "Reddit"]
    def results(self, platforms):
        assert self.handle == "orbit" and [p["name"] for p in platforms] == names
        verdicts = [("found", "api_user"), ("not_found", "api_absent"), ("unknown", "blocked"),
                    ("unknown", "out_of_time"), ("found", "differential")]
        return [self._hit(p, v, self._url_for(p, self.handle), 0, "", reason)
                for p, (v, reason) in zip(platforms, verdicts)], {}
    monkeypatch.setattr(tryout._TryoutSweep, "run", results)
    response = client.post("/api/handle-tryout/check", json={"handle": "orbit", "platforms": names})
    rows = response.get_json()["results"]
    assert [r["verdict"] for r in rows] == ["found", "not_found", "unknown", "unchecked", "unknown"]
    assert rows[0]["url"] == "https://github.com/orbit"
    assert all(set(r) == {"platform", "verdict", "reason"} for r in rows[1:])
    assert "no-store" in response.headers["Cache-Control"]
