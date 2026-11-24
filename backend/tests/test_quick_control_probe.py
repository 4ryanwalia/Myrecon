"""Quick-tier hits without account-specific evidence are settled by the sweep probe.

Offline: the page fetch and the sweep probe are stubbed. Measured live on
24 Nov 2026, the impossible handle "qzxvbnwkplrt" scored medium on HackerRank
and 15 more sites returned "low" hits for it; the probe found none of them.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import sweep  # noqa: E402
from modules import username_checker as uc  # noqa: E402
from services.search import _standard_platform_checks  # noqa: E402

URL = "https://www.hackerrank.com/{}"
# A generic page: long description, real-looking image, profile og:type and a
# canonical echoing the requested path. Corroboration only, so it scores
# "medium" without naming the handle in its title.
GENERIC = ('<html><head><title>HackerRank</title>'
           '<meta property="og:type" content="profile">'
           '<meta property="og:description" content="Join over 30 million developers solving code challenges.">'
           '<link rel="canonical" href="https://www.hackerrank.com/{h}"></head><body></body></html>')
TITLED = '<html><head><title>{h} | HackerRank profile</title></head><body>followers following</body></html>'


class _Resp:
    def __init__(self, text, url):
        self.text, self.url, self.status_code = text, url, 200


def _fetch(monkeypatch, template):
    monkeypatch.setattr(uc.requests, "get",
                        lambda url, **_: _Resp(template.format(h=url.rstrip("/").rsplit("/", 1)[-1]), url))


def _probe(monkeypatch, verdict, reason="", confidence="medium"):
    calls = []

    def probe(self, platform):
        calls.append(platform["name"])
        return {"verdict": verdict, "status_code": 200, "reason": reason, "confidence": confidence}
    monkeypatch.setattr(sweep.Sweep, "probe", probe)
    return calls


def _check(handle):
    checker = uc.UsernameChecker()
    result = checker._check_platform("HackerRank", URL.format(handle), 200, handle)
    checker.all_results = [result]
    return result, _standard_platform_checks(checker)[0]


def test_an_echo_page_becomes_unknown_not_a_finding(monkeypatch):
    _fetch(monkeypatch, GENERIC)
    calls = _probe(monkeypatch, sweep.UNKNOWN, "this platform shows the same page for any handle")
    result, check = _check("qzxvbnwkplrt")
    assert calls == ["HackerRank"]
    assert result["exists"] is False and "confidence" not in result
    assert check["verdict"] == "unknown"
    assert check["reason"] == "this platform shows the same page for any handle"


def test_a_probe_not_found_is_a_verified_absence(monkeypatch):
    _fetch(monkeypatch, GENERIC)
    _probe(monkeypatch, sweep.NOT_FOUND, "the platform returned its not-found status")
    result, check = _check("qzxvbnwkplrt")
    assert result["exists"] is False and result["match_score"] == -10
    assert check["verdict"] == "not_found"


@pytest.mark.parametrize("probe_confidence,expected", [("high", "high"), ("medium", "medium"), ("low", "medium")])
def test_a_probe_confirmed_hit_is_never_left_low(monkeypatch, probe_confidence, expected):
    _fetch(monkeypatch, GENERIC)
    _probe(monkeypatch, sweep.FOUND, "differs from this platform's no-such-user page", probe_confidence)
    result, check = _check("torvalds")
    assert result["exists"] is True and result["confidence"] == expected
    assert check["verdict"] == "found"


def test_direct_evidence_skips_the_probe(monkeypatch):
    _fetch(monkeypatch, TITLED)
    calls = _probe(monkeypatch, sweep.UNKNOWN)
    result = uc.UsernameChecker()._check_platform("Twitch", "https://www.twitch.tv/torvalds", 200, "torvalds")
    assert result["exists"] is True and result["confidence"] == "high"
    assert calls == []


def test_a_title_mention_on_an_echo_site_is_not_evidence(monkeypatch):
    # Telegram titles its no-such-user page "Telegram: Contact @handle".
    _fetch(monkeypatch, TITLED)
    calls = _probe(monkeypatch, sweep.UNKNOWN, "this platform shows the same page for any handle")
    result = uc.UsernameChecker()._check_platform("Telegram", "https://t.me/qzxvbnwkplrt", 200, "qzxvbnwkplrt")
    assert calls == ["Telegram"]
    assert result["exists"] is False


def test_a_platform_the_sweep_does_not_know_keeps_its_page_label(monkeypatch):
    _fetch(monkeypatch, GENERIC)
    calls = _probe(monkeypatch, sweep.UNKNOWN)
    checker = uc.UsernameChecker()
    result = checker._check_platform("NoSuchSweepPlatform", URL.format("someone"), 200, "someone")
    assert calls == []
    assert result["exists"] is True and result["confidence"] == uc._confidence_label(result["match_score"])
