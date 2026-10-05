import json
import subprocess
from types import SimpleNamespace

import httpx
import pytest

from modules import registered_accounts as adapter
from modules import holehe_worker as worker
from modules.email_lookup import _merge_registration_services, _linked_services
import app as appmod
import config

ROW = {"name": "Spotify", "id": "spotify", "domain": "spotify.com", "method": "register"}


def test_catalogue_has_123_pinned_modules_and_spotify_is_eligible():
    rows = adapter.CATALOG["services"]
    assert len(rows) == 123
    assert len({r["id"] for r in rows}) == len(rows)
    assert sum(r["enabled"] for r in rows) == 111
    assert next(r for r in rows if r["id"] == "spotify")["enabled"]
    assert all(not r["enabled"] for r in rows if r["method"] == "password recovery")


@pytest.mark.parametrize("raw,state", [({"exists": True}, "found"), ({"exists": False}, "no_signal"),
    ({"exists": False, "rateLimit": True}, "rate_limited"), ({"exists": True, "error": True}, "unavailable"),
    ({"exists": None}, "unavailable"), ({"exists": "true"}, "unavailable"), (None, "unavailable")])
def test_registration_verdict_never_promotes_errors(raw, state):
    assert worker.normalize(raw, ROW)["status"] == state


def test_recovery_details_and_raw_provider_payloads_are_not_returned():
    out = worker.normalize({"exists": True, "emailrecovery": "private@x.com", "phoneNumber": "555123", "others": {"FullName": "Secret"}}, ROW)
    assert "private" not in json.dumps(out)
    assert "555123" not in json.dumps(out)
    assert "Secret" not in json.dumps(out)


@pytest.mark.parametrize("provider_request", [
    httpx.Request("POST", "https://example.com/resetPassword", json={"email": "x@example.com"}),
    httpx.Request("POST", "https://example.com/register", json={"email": "x@example.com", "password": "generated"}),
    httpx.Request("GET", "https://example.com/login?passwd=secret"),
    httpx.Request("POST", "https://example.com/check", data={"send_email": "1"}),
    httpx.Request("GET", "http://example.com/check"),
    httpx.Request("POST", "https://example.com/check", json={"user": {"password": "secret"}}),
])
def test_request_guard_blocks_recovery_passwords_and_cleartext(provider_request):
    assert not worker.request_allowed(provider_request)


def test_spotify_validation_request_is_permitted():
    assert worker.request_allowed(httpx.Request("GET", "https://spclient.wg.spotify.com/signup/public/v1/account?validate=1&email=x@example.com"))


def test_worker_failure_preserves_unknown_for_every_service(monkeypatch):
    monkeypatch.setattr(adapter.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    out = adapter.scan_registered_accounts("x@example.com")
    assert out["status"] == "unavailable" and out["checked"] == 0
    assert len(out["services"]) == 123
    assert out["counts"]["unavailable"] == 111


def test_worker_receives_email_over_stdin_and_coverage_is_not_catalogue_size(monkeypatch):
    def run(args, **kwargs):
        assert "x@example.com" not in str(args)
        assert json.loads(kwargs["input"])["email"] == "x@example.com"
        assert kwargs["timeout"] == 42
        rows = adapter.baseline()
        spotify = next(r for r in rows if r["id"] == "spotify")
        spotify.update(status="found", reason="registration signal")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"services": rows}))
    monkeypatch.setattr(adapter.subprocess, "run", run)
    out = adapter.scan_registered_accounts("x@example.com")
    assert out["found"] == 1 and out["checked"] == 1 and out["partial"]


def test_historical_canva_and_spotify_registration_are_both_linked():
    history = _linked_services({}, None, {}, {"sources": [{"name": "Canva.com", "date": "2019"}, {"name": "Stealer logs"}]}, {}, {})
    out = _merge_registration_services(history, {"services": [
        {"service": "Spotify", "domain": "spotify.com", "status": "found", "reason": "registration signal"},
        {"service": "Canva", "domain": "canva.com", "status": "no_signal", "reason": "no signal"}]})
    assert {r["service"] for r in out["services"]} == {"Spotify", "Canva.com"}
    assert next(r for r in out["services"] if r["service"] == "Canva.com")["kind"] == "breach"


def test_registration_endpoint_validates_email_and_preserves_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(adapter, "scan_registered_accounts", lambda email: calls.append(email) or adapter.result(adapter.baseline(), "unavailable"))
    client = appmod.create_app().test_client()
    assert client.post("/api/email/accounts", json={"email": "bad"}).status_code == 422
    response = client.post("/api/email/accounts", json={"email": "x@example.com"})
    assert response.status_code == 200
    assert response.json["registration_checks"]["checked"] == 0
    assert calls == ["x@example.com"]



@pytest.mark.parametrize("payload", [[], {"services": [{}] * 123}, {"services": []}])
def test_malformed_worker_outputs_preserve_unavailable(monkeypatch, payload):
    monkeypatch.setattr(adapter.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload)))
    out = adapter.scan_registered_accounts("x@example.com")
    assert out["status"] == "unavailable" and out["checked"] == 0


def test_process_timeout_preserves_last_complete_checkpoint(monkeypatch):
    rows = adapter.baseline("timeout")
    rows[0].update(status="found", reason="registration signal")
    output = (json.dumps({"status": "partial", "services": rows}) + '\n{"services":').encode()
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 42, output=output)
    monkeypatch.setattr(adapter.subprocess, "run", timeout)
    out = adapter.scan_registered_accounts("x@example.com")
    assert out["status"] == "partial" and out["partial"]
    assert out["checked"] == out["found"] == 1
    assert out["counts"]["timeout"] == 110


def test_completed_worker_with_no_answers_is_unavailable(monkeypatch):
    monkeypatch.setattr(adapter.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps({"status": "ok", "services": adapter.baseline("timeout")})))
    out = adapter.scan_registered_accounts("x@example.com")
    assert out["status"] == "unavailable" and out["partial"]


def test_worker_reuses_tls_context_without_sharing_clients(monkeypatch, tmp_path):
    import hashlib
    import trio
    source = tmp_path / "provider.py"
    source.write_text("reviewed fixture", encoding="utf-8")
    rows = [{**ROW, "id": f"fixture{i}", "module": f"fixture{i}", "enabled": True,
             "sha256": hashlib.sha256(source.read_bytes()).hexdigest()} for i in range(2)]
    monkeypatch.setattr(worker, "CATALOG", {"services": rows})
    context = object()
    calls, clients = [], []
    monkeypatch.setattr(worker.ssl, "create_default_context", lambda: calls.append(True) or context)
    async def check(email, client, out):
        out.append({"exists": True})
    monkeypatch.setattr(worker.importlib, "import_module", lambda name: SimpleNamespace(
        __file__=str(source), **{name: check}))
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["verify"] is context
            assert kwargs["follow_redirects"] is False
            clients.append(self)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    out = trio.run(worker.run, "x@example.com", SimpleNamespace(AsyncClient=Client), trio)
    assert len(calls) == 1 and len(clients) == 2
    assert all(row["status"] == "found" for row in out)
