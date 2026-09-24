"""The username stream announces each hit as it lands.

The page draws a card the moment a "found" event arrives, so two things
matter: the event comes before "complete", and it carries only the fields a
card shows, never status codes, match scores or binary data.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.search as search  # noqa: E402


class _FakeChecker:
    def __init__(self, *a, **kw):
        self.all_results = []

    def scan(self, username, callback=None, deep=False):
        hit = {
            "platform": "GitHub", "url": f"https://github.com/{username}",
            "exists": True, "status_code": 200, "match_score": 4,
            "confidence": "high", "display_name": "Test User",
            "profile_pic_data": b"\x89PNG", "source": "username_check",
        }
        miss = {"platform": "Reddit", "url": "https://reddit.com/user/x",
                "exists": False, "status_code": 404, "reason": "404"}
        callback(module="Username Check", message="[1/2] Reddit, no match",
                 progress=50, results=[])
        callback(module="Username Check", message="[2/2] GitHub, found",
                 progress=100, results=[hit])
        self.all_results = [hit, miss]
        return [hit]


def test_found_event_precedes_complete_and_is_trimmed(monkeypatch):
    monkeypatch.setattr(search, "UsernameChecker", _FakeChecker)
    monkeypatch.setattr(search, "_enrich_profiles", lambda *a, **k: None)
    monkeypatch.setattr(search, "_code_exposure", lambda *a, **k: [])
    monkeypatch.setattr(search, "_has_google", lambda: False)

    events = list(search.stream_username("octocat"))
    types = [e["type"] for e in events]

    assert types.count("found") == 1
    assert types.index("found") < types.index("complete")

    live = next(e for e in events if e["type"] == "found")["result"]
    assert live["platform"] == "GitHub"
    assert live["confidence"] == "high"
    assert "category" in live
    for leaked in ("status_code", "match_score", "profile_pic_data", "exists"):
        assert leaked not in live
