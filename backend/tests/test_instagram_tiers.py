"""Instagram must reach the user in every tier, and never on weak evidence.

Offline: the sweep probe is stubbed, so these pin the mapping and the guest
preview rules rather than Instagram's live behaviour.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
from modules import sweep  # noqa: E402
from modules.username_checker import UsernameChecker  # noqa: E402

URL = "https://www.instagram.com/{}/"


def _stub_probe(monkeypatch, verdict, status=200, reason="", **extra):
    def probe(self, platform):
        assert platform["name"] == "Instagram"
        return {"verdict": verdict, "status_code": status, "reason": reason,
                "confidence": "high", "profile_pic_url": None, "display_name": None, **extra}
    monkeypatch.setattr(sweep.Sweep, "probe", probe)


def _check(handle):
    return UsernameChecker()._check_platform("Instagram", URL.format(handle), 200, handle)


def test_quick_tier_reports_instagram_found_by_the_sweep_probe(monkeypatch):
    _stub_probe(monkeypatch, sweep.FOUND, display_name="NASA (&#064;nasa) &#x2022; Instagram",
                profile_pic_url="https://scontent.cdninstagram.com/nasa.jpg")
    r = _check("nasa")
    assert r["exists"] is True and r["confidence"] == "high"
    assert r["display_name"] == "NASA (@nasa) • Instagram"
    assert r["profile_pic_url"].endswith("nasa.jpg")


@pytest.mark.parametrize("reason", ["this platform shows the same page for any handle",
                                    "redirected to a login page"])
def test_quick_tier_keeps_an_unreadable_instagram_unknown(monkeypatch, reason):
    # The old scoring called the logged-out shell "possible" and a login
    # bounce "no account". Both are unknown.
    _stub_probe(monkeypatch, sweep.UNKNOWN, reason=reason)
    r = _check("zxqvbnmlkjhg")
    assert r["exists"] is False and r.get("match_score") is None
    assert r["reason"] == reason


def test_quick_tier_reports_instagram_absent_only_on_negative_evidence(monkeypatch):
    _stub_probe(monkeypatch, sweep.NOT_FOUND, status=404, reason="no such account")
    r = _check("zxqvbnmlkjhg")
    assert r["exists"] is False and r["status_code"] == 404 and r["match_score"] == -10


def _card(name):
    return {"platform": name, "url": f"https://{name.lower()}.example/h",
            "category": "profile", "confidence": "high"}


def test_guest_preview_always_shows_a_found_instagram():
    cards = [_card("TikTok"), _card("Flickr"), _card("Hidden"), _card("Instagram")]
    data = {"status": "ok", "query": {"username": "h"}, "summary": {},
            "results": {"profiles": cards, "documents": [], "mentions": []},
            "platform_checks": [{"platform": "Instagram", "verdict": "found", "url": "x"}]}
    # Live scan order: Instagram answered last, after the two free cards.
    seen, visible = set(), []
    events = [app_module._guest_quick_event({"type": "found", "result": c}, seen, visible)
              for c in cards]
    assert events[3]["type"] == "found" and events[3]["result"]["platform"] == "Instagram"
    assert events[2]["type"] == "found_locked"
    shown = app_module._guest_quick_preview(data, visible)
    names = [c["platform"] for c in shown["results"]["profiles"]]
    assert names == ["TikTok", "Flickr", "Instagram"]
    assert shown["guest_preview"]["hidden_cards"] == 1
    assert shown["instagram_check"] == {"verdict": "found"}
    assert "hidden.example" not in str(shown)


def test_guest_preview_passes_only_the_instagram_verdict():
    data = {"results": {"profiles": [_card("A"), _card("B"), _card("C")]},
            "platform_checks": [{"platform": "Instagram", "verdict": "unknown",
                                 "url": "https://www.instagram.com/h/", "reason": "secret"}]}
    shown = app_module._guest_quick_preview(data)
    assert [c["platform"] for c in shown["results"]["profiles"]] == ["A", "B"]
    assert shown["instagram_check"] == {"verdict": "unknown"}
    assert app_module._guest_quick_preview({"results": {}})["instagram_check"] is None
