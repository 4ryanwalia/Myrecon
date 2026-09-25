"""Contracts for the per-platform username-scan audit trail.

These tests deliberately use tiny in-memory scanner fixtures.  They pin the
report boundary rather than making real network requests to platform sites.
"""

import json
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import config  # noqa: E402
import services.search as search  # noqa: E402
from modules.sweep import CATALOGUE  # noqa: E402


class _FixtureChecker:
    """A standard scan with one outcome from each truthful verdict class."""

    OUTCOMES = [
        {
            "platform": "Confirmed platform",
            "url": "https://confirmed.example/octocat",
            "exists": True,
            "status_code": 200,
            "match_score": 4,
            "confidence": "high",
            "source": "username_check",
        },
        {
            "platform": "Weak-evidence platform",
            "url": "https://weak.example/octocat",
            "exists": True,
            "status_code": 200,
            "match_score": 0,
            "confidence": "low",
            "source": "username_check",
        },
        {
            "platform": "Absent platform",
            "url": "https://absent.example/octocat",
            "exists": False,
            "status_code": 404,
            "reason": "the platform returned its not-found status",
            "source": "username_check",
        },
        {
            "platform": "Blocked platform",
            "url": "https://blocked.example/octocat",
            "exists": False,
            "status_code": 403,
            "reason": "the platform blocked or rate-limited the check",
            "source": "username_check",
        },
    ]

    def __init__(self, *_args, **_kwargs):
        self.all_results = []

    def scan(self, _username, callback=None, deep=False):
        self.all_results = [dict(row) for row in self.OUTCOMES]
        if callback:
            for index, row in enumerate(self.all_results, start=1):
                callback(
                    module="Username Check",
                    message=f"[{index}/{len(self.all_results)}] {row['platform']}",
                    progress=index * 25,
                    results=[row] if row["exists"] else [],
                )
        return [row for row in self.all_results if row["exists"]]


class _NoClusters:
    def correlate(self, *_args, **_kwargs):
        return []


def _full_result_with_every_check():
    checks = [
        {
            "platform": platform["name"],
            "category": platform["category"],
            "url": platform["url"].replace("{username}", "octocat"),
            "verdict": "not_found",
            "status_code": 404,
            "reason": "the platform returned its not-found status",
            "unreachable": False,
        }
        for platform in CATALOGUE
    ]
    return {
        "status": "ok",
        "query": {"username": "octocat", "deep": True, "scope": "full"},
        "summary": {"total": 0, "profiles": 0, "checked": len(checks), "clusters": 0},
        "coverage": {"total": len(checks), "found": 0, "not_found": len(checks)},
        "results": {"profiles": [], "documents": [], "mentions": []},
        "identity_clusters": [],
        "exposures": [],
        "rejected": [],
        "unverified": [],
        "platform_checks": checks,
    }


def test_standard_platform_checks_cover_every_actual_outcome_with_truthful_verdicts(monkeypatch):
    monkeypatch.setattr(search, "UsernameChecker", _FixtureChecker)
    monkeypatch.setattr(search, "_enrich_profiles", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "_code_exposure", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(search, "_has_google", lambda: False)
    monkeypatch.setattr(search, "IdentityCorrelator", lambda: _NoClusters())
    monkeypatch.setattr(search, "categorise_result", lambda *_args, **_kwargs: "profile")

    result = search._run_username("octocat", deep=True)

    checks = {row["platform"]: row for row in result["platform_checks"]}
    assert result["summary"]["checked"] == len(_FixtureChecker.OUTCOMES)
    assert set(checks) == {row["platform"] for row in _FixtureChecker.OUTCOMES}
    assert checks["Confirmed platform"]["verdict"] == "found"
    assert checks["Weak-evidence platform"]["verdict"] == "possible"
    assert checks["Absent platform"]["verdict"] == "not_found"
    assert checks["Blocked platform"]["verdict"] == "unknown"
    assert checks["Absent platform"]["reason"] == "the platform returned its not-found status"
    assert checks["Blocked platform"]["reason"] == "the platform blocked or rate-limited the check"


def test_guest_full_response_exposes_only_the_first_hundred_platform_checks(monkeypatch):
    full = _full_result_with_every_check()
    visible_names = {platform["name"] for platform in CATALOGUE[:100]}
    hidden_name = CATALOGUE[100]["name"]

    monkeypatch.setattr(config, "CACHE_ENABLED", False)
    monkeypatch.setattr(app_module, "_admit_scan", lambda *_args, **_kwargs: (None, None))
    monkeypatch.setattr(app_module, "_remember", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "_run_full", lambda *_args, **_kwargs: full)

    response = app_module.app.test_client().post(
        "/api/username", json={"username": "octocat", "scope": "full"}
    )

    assert response.status_code == 200
    body = response.get_json()
    checks = body["platform_checks"]
    assert len(checks) == 100
    assert {row["platform"] for row in checks} == visible_names
    assert hidden_name not in {row["platform"] for row in checks}
    assert hidden_name not in json.dumps(body)


def test_signed_in_full_response_preserves_every_platform_check(monkeypatch):
    full = _full_result_with_every_check()
    hidden_name = CATALOGUE[100]["name"]

    monkeypatch.setattr(config, "CACHE_ENABLED", False)
    monkeypatch.setattr(app_module, "_admit_scan", lambda *_args, **_kwargs: ("user-1", None))
    monkeypatch.setattr(app_module, "_remember", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(search, "_run_full", lambda *_args, **_kwargs: full)

    response = app_module.app.test_client().post(
        "/api/username", json={"username": "octocat", "scope": "full"}
    )

    assert response.status_code == 200
    checks = response.get_json()["platform_checks"]
    assert len(checks) == len(CATALOGUE)
    assert {row["platform"] for row in checks} == {platform["name"] for platform in CATALOGUE}
    assert hidden_name in {row["platform"] for row in checks}
