"""Offline regressions for breach coverage, malformed responses and retry caching."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.email_lookup import EmailLookup, _worst_status
import app as appmod
import config


class Response:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}
        self.payload = payload

    def json(self):
        return self.payload


@pytest.mark.parametrize("method,payload", [
    ("breaches", {}), ("breaches", {"success": True}),
    ("breaches", {"success": True, "found": "many"}),
    ("breaches", {"success": True, "found": 2, "sources": [None]}),
    ("xposed_check_email", {"Error": "service unavailable"}),
    ("xposed_check_email", {"breaches": [{"unknown": True}]}),
    ("darkweb", {}), ("darkweb", {"ExposedBreaches": {}}),
    ("darkweb", {"ExposedBreaches": {"breaches_details": [None]}}),
])
def test_malformed_success_replies_are_unavailable(monkeypatch, method, payload):
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: Response(payload))
    result = getattr(EmailLookup(), method)("fixture@example.com")
    assert result["status"] == "unavailable"
    assert result["breached"] is False


def test_analytics_explicit_empty_answer_is_checked(monkeypatch):
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: Response({"ExposedBreaches": None}))
    result = EmailLookup().darkweb("fixture@example.com")
    assert result["status"] == "ok"
    assert result["checked"] is True
    assert result["breached"] is False


@pytest.mark.parametrize("primary_state,analytics_state,found,expected,completed", [
    ("ok", "ok", False, "no_match", 2),
    ("ok", "unavailable", False, "incomplete", 1),
    ("unavailable", "unavailable", False, "unavailable", 0),
    ("ok", "unavailable", True, "found", 1),
])
def test_summary_counts_attempted_and_completed_sources(monkeypatch, primary_state, analytics_state, found, expected, completed):
    intel = EmailLookup()
    monkeypatch.setattr(intel, "analyze", lambda e: {"deliverable": False, "disposable": False})
    monkeypatch.setattr(intel, "gravatar", lambda e: {"exists": False, "accounts": []})
    monkeypatch.setattr(intel, "github", lambda e: None)
    monkeypatch.setattr(intel, "breaches", lambda e: {
        "status": primary_state, "checked": primary_state == "ok", "breached": found,
        "count": int(found), "sources": [{"name": "Fixture"}] if found else [],
    })
    monkeypatch.setattr(intel, "darkweb", lambda e: {
        "status": analytics_state, "checked": analytics_state == "ok", "breached": False,
        "count": 0, "breaches": [], "records_exposed": 0, "risk_label": "", "risk_score": 0,
    })
    monkeypatch.setattr(intel, "xposed_check_email", lambda e: {
        "status": "unavailable", "breached": False, "sources": [], "retry_after": 4,
    })
    summary = intel.scan("fixture@example.com")["summary"]
    assert summary["breach_outcome"] == expected
    assert summary["breach_coverage"]["completed"] == completed
    assert summary["breach_coverage"]["attempted"] == (2 if primary_state == "ok" else 3)
    if primary_state != "ok":
        assert summary["retry_after"] == 4


def test_checked_false_cannot_become_an_ok_aggregate():
    assert _worst_status({"status": "ok", "checked": False}, None, {}) == "unavailable"
    assert _worst_status({"status": "skipped"}, None, {}) == "unavailable"


def test_incomplete_results_are_retried_instead_of_cached(monkeypatch):
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    appmod._cache.clear()
    calls = []

    @appmod.cached("email")
    def scan(email):
        calls.append(email)
        return {"summary": {"breach_status": "partial_unavailable" if len(calls) == 1 else "ok"}}

    assert scan("fixture@example.com")["summary"]["breach_status"] == "partial_unavailable"
    assert scan("fixture@example.com")["summary"]["breach_status"] == "ok"
    scan("fixture@example.com")
    assert len(calls) == 2
    appmod._cache.clear()
