import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.email_lookup import EmailLookup, _linked_services
from services import email as service
import config
import app as appmod

EMAIL = "fixture@gmail.com"


class Response:
    def __init__(self, body=None, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


def replies(monkeypatch, *responses):
    responses = iter(responses)
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return next(responses)
    monkeypatch.setattr("modules.email_lookup.requests.get", get)
    return calls


def test_exact_public_gmail_profile(monkeypatch):
    replies(monkeypatch, Response({"items": [{"login": "fixture"}]}),
            Response({"login": "fixture", "email": EMAIL}))
    account = EmailLookup().github(EMAIL)
    assert account["status"] == "found"
    assert account["username"] == "fixture"
    assert "Exact email" in account["evidence"]


def test_commit_fallback_requires_exact_email_and_attributed_author(monkeypatch):
    item = {"author": {"login": "dev"}, "commit": {"author": {"email": EMAIL}},
            "html_url": "https://github.com/dev/repo/commit/abc"}
    calls = replies(monkeypatch, Response({"items": []}), Response({"items": [
        {**item, "commit": {"author": {"email": "other@gmail.com"}}},
        {**item, "author": None}, item]}), Response({"login": "dev"}))
    account = EmailLookup().github(EMAIL)
    assert account["username"] == "dev"
    assert "current account email is unknown" in account["evidence"]
    assert calls[-2][1]["params"]["q"] == f'author-email:"{EMAIL}"'


def test_unverified_user_search_result_is_not_account_proof(monkeypatch):
    replies(monkeypatch, Response({"items": [{"login": "fixture"}]}),
            Response({"email": "other@gmail.com"}), Response({"items": []}))
    assert EmailLookup().github(EMAIL) == {"status": "no_match"}


@pytest.mark.parametrize("response,expected", [
    (Response(status=429), "rate_limited"), (Response(status=403), "rate_limited"),
    (Response(status=503), "unavailable"), (Response({"message": "bad"}), "unavailable"),
    (Response({"items": [], "incomplete_results": True}), "unavailable"),
])
def test_failed_github_search_never_becomes_no_match(monkeypatch, response, expected):
    calls = replies(monkeypatch, response)
    assert EmailLookup().github(EMAIL)["status"] == expected
    assert len(calls) == 1


def test_timeout_is_unavailable(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout()
    monkeypatch.setattr("modules.email_lookup.requests.get", timeout)
    assert EmailLookup().github(EMAIL)["status"] == "unavailable"


@pytest.mark.parametrize("response,expected", [
    (Response({"entry": []}), "unavailable"),
    (Response({"entry": [{}]}), "unavailable"),
    (Response(status=503), "unavailable"),
    (Response(status=404), "no_match"),
    (Response(status=429), "rate_limited"),
])
def test_gravatar_empty_or_failed_responses_do_not_prove_a_profile(monkeypatch, response, expected):
    replies(monkeypatch, response)
    result = EmailLookup().gravatar(EMAIL)
    assert result["exists"] is False
    assert result["status"] == expected


def test_switch_off_skips_all_public_account_network_calls(monkeypatch):
    lookup = EmailLookup()
    monkeypatch.setattr(lookup, "analyze", lambda e: {"deliverable": True, "disposable": False})
    monkeypatch.setattr(lookup, "breaches", lambda e: {"status": "ok", "checked": True, "sources": [{"name": "Adobe"}], "breached": True})
    monkeypatch.setattr(lookup, "darkweb", lambda e: {"status": "ok", "checked": True})
    def forbidden(email):
        pytest.fail("Disabled account checks made a provider request")
    for name in ("github", "gravatar", "pgp"):
        monkeypatch.setattr(lookup, name, forbidden)
    result = lookup.scan(EMAIL, check_linked_accounts=False)
    assert result["summary"]["breached"]
    assert result["github"] is None
    assert result["summary"]["linked_accounts"] == []
    assert result["registration_checks"]["status"] == "skipped"
    assert result["account_checks"]["enabled"] is False
    assert all(s["status"] == "skipped" for s in result["account_checks"]["sources"])


def test_failed_github_is_not_a_linked_service():
    result = _linked_services({}, {"status": "unavailable"}, {}, {}, {}, {})
    assert result["services"] == []


@pytest.mark.parametrize("option", [False, True])
def test_route_passes_account_choice(monkeypatch, option):
    calls = []
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(service, "scan_email", lambda email, check_linked_accounts: calls.append(check_linked_accounts) or {})
    response = appmod.create_app().test_client().post("/api/email", json={"email": EMAIL, "check_linked_accounts": option})
    assert response.status_code == 200
    assert calls == [option]


def test_email_api_defaults_to_live_account_checks_off(monkeypatch):
    import services.email as service
    calls = []
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(service, "scan_email", lambda email, check_linked_accounts: calls.append(check_linked_accounts) or {})
    response = appmod.create_app().test_client().post("/api/email", json={"email": EMAIL})
    assert response.status_code == 200
    assert calls == [False]


def test_registration_outage_marks_email_partial_without_losing_breach_matches(monkeypatch):
    lookup = EmailLookup()
    monkeypatch.setattr(lookup, "analyze", lambda e: {"deliverable": True, "disposable": False})
    monkeypatch.setattr(lookup, "breaches", lambda e: {"status": "ok", "checked": True,
        "sources": [{"name": "Canva"}], "breached": True})
    monkeypatch.setattr(lookup, "darkweb", lambda e: {"status": "ok", "checked": True})
    monkeypatch.setattr(lookup, "github", lambda e: {"status": "no_match"})
    monkeypatch.setattr(lookup, "gravatar", lambda e: {"status": "no_match", "exists": False})
    monkeypatch.setattr(lookup, "pgp", lambda e: {"status": "ok", "exists": False})
    monkeypatch.setattr("modules.registered_accounts.scan_registered_accounts", lambda e:
        {"status": "unavailable", "partial": True, "services": [], "checked": 0, "attempted": 111})
    out = lookup.scan(EMAIL, check_linked_accounts=True)
    assert out["partial"]
    assert any(error["source"] == "Registration checks" for error in out["errors"])
    assert out["summary"]["breached"] and out["summary"]["breach_status"] == "ok"
    assert out["linked_services"]["count"] == 1
