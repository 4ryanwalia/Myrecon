"""Offline failures must preserve findings, bound work and avoid sensitive logs."""
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import google_dork as google
from modules.email_lookup import EmailLookup
from modules.enrichment import _PrivateDiagnostics
import services.search as search
import services.email as email_service
import app as appmod
import config


class Response:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.payload = payload if payload is not None else {"items": [{"link": "https://example.com/verified"}]}

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def reset_google(monkeypatch):
    monkeypatch.setattr(google, "_NEXT_START", 0)
    monkeypatch.setattr(google, "_COOLDOWN_UNTIL", 0)
    monkeypatch.setattr(google, "_MIN_INTERVAL", 0)
    monkeypatch.setattr(google.random, "uniform", lambda *a: 0)


def engine():
    return google.GoogleDorkEngine("private-api-key", "test-cx", delay=0)


def test_individual_dork_failure_preserves_success_and_deduplicates(monkeypatch):
    def get(*args, **kwargs):
        query = kwargs["params"]["q"]
        if query == "bad":
            raise requests.Timeout("https://provider/?key=private-api-key&q=secret-handle")
        return Response()
    monkeypatch.setattr(google.requests, "get", get)
    dork = engine()
    assert len(dork._run_dorks(["good", "bad", "duplicate"])) == 1
    assert dork.errors[0]["code"] == "unavailable"
    assert "private-api-key" not in str(dork.errors)
    assert "secret-handle" not in str(dork.errors)


@pytest.mark.parametrize("status", [403, 429])
def test_denials_open_shared_cooldown_without_retries(monkeypatch, status):
    calls = []
    monkeypatch.setattr(google.requests, "get", lambda *a, **k: calls.append(k) or Response(status, headers={"Retry-After": "90"}))
    assert engine()._execute_query("private-handle")[0]["code"] in ("provider_denied", "rate_limited")
    assert engine()._execute_query("another-handle")[0]["code"] == "rate_limited"
    assert len(calls) == 1
    assert google._COOLDOWN_UNTIL >= time.monotonic() + 89


def test_transient_failure_retries_once_and_returns_success(monkeypatch):
    calls = []
    def get(*a, **k):
        calls.append(k)
        return Response(503) if len(calls) == 1 else Response()
    monkeypatch.setattr(google.requests, "get", get)
    result = engine()._execute_query("test")
    assert result[0]["url"].startswith("https://")
    assert len(calls) == 2
    assert all(0 < timeout <= 8 for timeout in calls[0]["timeout"])


def test_scan_deadline_returns_partial_without_waiting_for_worker(monkeypatch):
    release = threading.Event()
    finished = threading.Event()
    dork = engine()
    dork.deadline_seconds = 0.06
    def execute(query, deadline):
        if query == "fast":
            return [{"url": "https://example.com/fast"}]
        release.wait(2)
        finished.set()
        return [{"url": "https://example.com/late"}]
    monkeypatch.setattr(dork, "_execute_query", execute)
    start = time.monotonic()
    try:
        results = dork._run_dorks(["fast", "slow"])
        assert time.monotonic() - start < 0.6
        assert [r["url"] for r in results] == ["https://example.com/fast"]
        assert dork.errors[0]["code"] == "timeout"
    finally:
        release.set()
        assert finished.wait(1)


def test_concurrent_scans_share_http_request_limit(monkeypatch):
    lock = threading.Lock()
    active = peak = 0
    def get(*a, **k):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        time.sleep(0.02)
        with lock:
            active -= 1
        return Response()
    monkeypatch.setattr(google.requests, "get", get)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: engine()._run_dorks(["a", "b", "c", "d"]), range(3)))
    assert all(results)
    assert 1 < peak <= google._CONCURRENCY


@pytest.mark.parametrize("payload", [{}, {"items": [None]}, {"items": "bad"}, {"error": {"message": "secret"}}])
def test_unreadable_google_reply_is_an_error_not_empty_success(monkeypatch, payload):
    monkeypatch.setattr(google.requests, "get", lambda *a, **k: Response(payload=payload))
    assert engine()._execute_query("query")[0]["code"] == "invalid_response"


def test_missing_credentials_do_not_return_simulated_findings(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CX_ID", raising=False)
    dork = google.GoogleDorkEngine()
    assert dork._run_dorks(["query"]) == []
    assert dork.errors[0]["code"] == "unconfigured"


def test_email_unexpected_failure_keeps_other_provider_results(monkeypatch):
    lookup = EmailLookup()
    def fail(email):
        raise TypeError("secret-email@example.com")
    monkeypatch.setattr(lookup, "analyze", lambda e: {"deliverable": True, "disposable": False})
    monkeypatch.setattr(lookup, "gravatar", lambda e: {"exists": True, "accounts": []})
    monkeypatch.setattr(lookup, "breaches", fail)
    monkeypatch.setattr(lookup, "darkweb", lambda e: {"status": "ok", "checked": True, "breached": False})
    monkeypatch.setattr(lookup, "xposed_check_email", lambda e: {"status": "ok", "checked": True, "breached": True, "count": 1, "sources": [{"name": "Fixture"}]})
    monkeypatch.setattr(lookup, "github", lambda e: None)
    monkeypatch.setattr(lookup, "pgp", lambda e: {"exists": False})
    result = lookup.scan("fixture@example.com")
    assert result["gravatar"]["exists"]
    assert result["summary"]["breached"]
    assert result["summary"]["breach_status"] == "partial_unavailable"
    assert result["partial"] is True
    assert result["errors"][0]["source"] == "LeakCheck"
    assert "secret-email" not in str(result["errors"])


def test_email_route_never_caches_even_successful_lookups(monkeypatch):
    calls = []
    monkeypatch.setattr(email_service, "scan_email", lambda e, check_linked_accounts=True: calls.append((e, check_linked_accounts)) or {"status": "ok", "summary": {"breach_status": "ok"}})
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    client = appmod.create_app().test_client()
    for _ in range(2):
        assert client.post("/api/email", json={"email": "fixture@example.com"}).status_code == 200
    assert len(calls) == 2
    assert all(option is True for _, option in calls)


def test_username_soft_failure_survives_stream_completion(monkeypatch):
    class Checker:
        all_results = []
        def __init__(self, **kwargs):
            pass
        def scan(self, *args, **kwargs):
            return [{"platform": "Example", "url": "https://example.com/test", "exists": True, "source": "username_check"}]
    class Dork:
        errors = [{"source": "google_dork", "code": "unavailable", "message": "Web search unavailable"}]
        def __init__(self, **kwargs):
            pass
        def scan_username(self, *args, **kwargs):
            return []
    monkeypatch.setattr(search, "UsernameChecker", Checker)
    monkeypatch.setattr(search, "GoogleDorkEngine", Dork)
    monkeypatch.setattr(search, "_has_google", lambda: True)
    monkeypatch.setattr(search, "_enrich_profiles", lambda *a: None)
    monkeypatch.setattr(search, "_code_exposure", lambda *a: [])
    monkeypatch.setattr(search.IdentityCorrelator, "correlate", lambda *a, **k: [])
    events = list(search.stream_username("test"))
    data = events[-1]["data"]
    assert events[-1]["type"] == "complete"
    assert data["partial"] is True
    assert data["results"]["profiles"][0]["platform"] == "Example"
    assert data["errors"][0]["source"] == "google_dork"


def test_profile_diagnostics_remove_identifiers():
    record = logging.LogRecord("enrichment.instagram", logging.INFO, __file__, 1,
                               "Enriching %s", ("secret-handle",), None)
    assert _PrivateDiagnostics().filter(record)
    assert "secret-handle" not in record.getMessage()


def test_partial_search_results_are_not_cached(monkeypatch):
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    calls = []
    appmod._cache.clear()
    @appmod.cached("username")
    def scan(username):
        calls.append(username)
        return {"status": "ok", "partial": True}
    scan("fixture")
    scan("fixture")
    assert len(calls) == 2
