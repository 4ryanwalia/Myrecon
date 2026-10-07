"""Email findings are public, unmetered and never retained for paid reveal."""

from copy import deepcopy

import pytest
import requests

import app as appmod
import config
from core import guest_reports, history, plans, store
from core.ratelimit import RateLimiter
from modules import email_photos, registered_accounts
from services import email, email_linkedin_public, email_public_profiles


EMAIL = "fixture@example.com"
AUTH_HEADERS = [{}, {"Authorization": "Bearer expired-or-invalid-token"},
                {"Authorization": "Basic malformed"}]
POST_ROUTES = ["/api/email", "/api/email/public-profiles",
               "/api/email/linkedin-public", "/api/email/accounts"]


@pytest.fixture
def client_factory(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "SCAN_OFFLOAD_ENABLED", False)

    def forbidden(*args, **kwargs):
        pytest.fail("Free email lookup attempted authentication, billing, retention or real network access")

    for name in ("_signed_in_user", "_require_user", "_admit_scan", "_remember", "_standard_response"):
        monkeypatch.setattr(appmod, name, forbidden)
    for name in ("get_account", "entitlements", "consume_guest_scan", "consume_standard_scan", "consume_extended_scan"):
        monkeypatch.setattr(plans, name, forbidden)
    for name in ("standard", "deep", "retain"):
        monkeypatch.setattr(guest_reports, name, forbidden)
    monkeypatch.setattr(history, "save", forbidden)
    monkeypatch.setattr(store, "persistent", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    # Main lookup is imported into each app's route closure. Construct after
    # installing the provider stub so no test can use the real lookup.
    return lambda: appmod.create_app().test_client()


@pytest.mark.parametrize("headers", AUTH_HEADERS)
@pytest.mark.parametrize("option", [None, False, True])
def test_every_email_finding_and_source_outcome_is_returned_without_account_access(client_factory, monkeypatch, headers, option):
    report = {
        "status": "ok", "query": {"email": EMAIL}, "partial": True,
        "analysis": {"domain": "example.com", "deliverable": None},
        "breaches": {"status": "ok", "sources": [{"name": name} for name in ("Alpha", "Beta", "Gamma", "Delta")]},
        "linked_services": {"count": 4, "services": [{"service": name, "kind": "breach"} for name in ("Alpha", "Beta", "Gamma", "Delta")]},
        "summary": {"breach_outcome": "found", "breach_status": "partial_unavailable",
                    "breach_count": 4, "breach_coverage": {"completed": 1, "attempted": 2,
                    "sources": [{"name": "LeakCheck", "status": "ok"}, {"name": "XposedOrNot", "status": "unavailable"}]}},
        "errors": [{"source": "XposedOrNot", "code": "unavailable", "retryable": True}],
    }
    original = deepcopy(report)
    calls = []
    monkeypatch.setattr(email, "scan_email", lambda value, check_linked_accounts:
                        calls.append((value, check_linked_accounts)) or report)
    body = {"email": EMAIL}
    if option is not None:
        body["check_linked_accounts"] = option
    response = client_factory().post("/api/email", json=body, headers=headers)
    assert response.status_code == 200
    assert response.json == original
    assert report == original
    assert calls == [(EMAIL, option is True)]
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("headers", AUTH_HEADERS)
@pytest.mark.parametrize("route,module,function", [
    ("/api/email/public-profiles", email_public_profiles, "lookup_public_profiles"),
    ("/api/email/linkedin-public", email_linkedin_public, "lookup_linkedin_public"),
    ("/api/email/accounts", registered_accounts, "scan_registered_accounts"),
])
def test_related_email_results_are_complete_and_free(client_factory, monkeypatch, headers, route, module, function):
    result = {"status": "partial", "profiles": [{"platform": name} for name in ("Alpha", "Beta", "Gamma")],
              "sources": [{"name": "Fixture source", "status": "unavailable"}], "checked": 0}
    calls = []
    monkeypatch.setattr(module, function, lambda value: calls.append(value) or result)
    response = client_factory().post(route, json={"email": EMAIL}, headers=headers)
    assert response.status_code == 200
    expected = {"status": "ok", "registration_checks": result} if route.endswith("/accounts") else result
    assert response.json == expected
    assert calls == [EMAIL]
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("headers", AUTH_HEADERS)
def test_public_email_photo_needs_no_account(client_factory, monkeypatch, headers):
    calls = []
    url = "https://avatars.githubusercontent.com/fixture"
    monkeypatch.setattr(email_photos, "fetch_public_photo", lambda value:
                        calls.append(value) or email_photos.Photo(b"fixture image", "image/png"))
    response = client_factory().get("/api/email/photo", query_string={"url": url}, headers=headers)
    assert response.status_code == 200
    assert response.data == b"fixture image"
    assert response.content_type == "image/png"
    assert "no-store" in response.headers["Cache-Control"]
    assert calls == [url]


def test_public_photo_failure_preserves_safe_source_error(client_factory, monkeypatch):
    def failed(value):
        raise email_photos.PhotoError("unsupported_photo_url", 400)
    monkeypatch.setattr(email_photos, "fetch_public_photo", failed)
    response = client_factory().get("/api/email/photo", query_string={"url": "https://private.invalid/fixture"})
    assert response.status_code == 400
    assert response.json["code"] == "unsupported_photo_url"
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("route", POST_ROUTES)
def test_free_email_routes_still_validate_queries(client_factory, route):
    response = client_factory().post(route, json={"email": "invalid"}, headers=AUTH_HEADERS[1])
    assert response.status_code == 422


@pytest.mark.parametrize("route", POST_ROUTES + ["/api/email/photo"])
def test_free_email_preflight_needs_no_account(client_factory, route):
    assert client_factory().options(route, headers=AUTH_HEADERS[1]).status_code == 204


def test_free_email_keeps_generic_ip_throttling(client_factory, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(appmod, "_limiter", RateLimiter(1, 60))
    calls = []
    monkeypatch.setattr(email, "scan_email", lambda value, check_linked_accounts:
                        calls.append(value) or {"status": "ok"})
    client = client_factory()
    assert client.post("/api/email", json={"email": EMAIL}).status_code == 200
    limited = client.post("/api/email", json={"email": EMAIL})
    assert limited.status_code == 429
    assert limited.json["code"] == "rate_limited"
    assert calls == [EMAIL]
