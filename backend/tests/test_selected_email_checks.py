import json

import httpx
import pytest
import trio

from modules import selected_email_checks as selected
from modules import registered_accounts as adapter
from modules import holehe_worker as worker
from modules.email_lookup import _merge_registration_services


@pytest.mark.parametrize("service,code,payload,expected", [
    ("huggingface", 200, "This email address already exists", True),
    ("huggingface", 200, {"message": "This email address is available."}, False),
    ("huggingface", 200, {}, None),
    ("huggingface", 500, "already exists", None),
    ("hackerrank", 200, {"status": False}, None),
    ("hackerrank", 200, {"status": False, "errors": ["Invalid email"]}, None),
    ("hackerrank", 200, {"internal_status_code": "already_registered"}, True),
    ("hackerrank", 200, {"status": True}, False),
    ("hackerrank", 200, {"status": True, "errors": "already registered"}, None),
])
def test_only_explicit_signals(service, code, payload, expected):
    response = httpx.Response(code, json=payload)
    raw = selected.verdict(service, response)
    assert raw == ({"exists": expected} if expected is not None else None)


def test_selected_catalogue_is_missing_from_holehe_and_preserves_it():
    assert len(adapter.HOLEHE_SERVICES) == 123
    assert len(adapter.CATALOG["services"]) == 125
    assert not ({r["id"] for r in selected.SERVICES} & {r["id"] for r in adapter.HOLEHE_SERVICES})


def test_requests_are_email_only_guarded_and_never_redirected():
    async def run():
        for row in selected.SERVICES:
            calls = []
            async def transport(request):
                assert worker.request_allowed(request)
                assert selected.permitted(request, row)
                assert "x@example.com" not in str(request.url)
                calls.append(request)
                return httpx.Response(302, headers={"location": "https://example.com/reset"})
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport), follow_redirects=False) as client:
                assert await selected.check("x@example.com", client, row) is None
            assert len(calls) == 1
            for request in [
                httpx.Request("POST", row["endpoint"], json={"email": "x@example.com", "password": ""}),
                httpx.Request("POST", row["endpoint"] + "?email=x@example.com", json={"email": "x@example.com"}),
                httpx.Request("POST", "https://example.com/check", json={"email": "x@example.com"}),
            ]:
                assert not selected.permitted(request, row)
    trio.run(run)


def test_failures_and_positive_results_stay_in_registration_schema():
    for code in (403, 429, 500):
        raw = selected.verdict("hackerrank", httpx.Response(code, json={"status": True}))
        row = worker.normalize(raw, selected.SERVICES[1])
        assert row["status"] == ("rate_limited" if code in (403, 429) else "unavailable")
    row = worker.normalize({"exists": True, "email": "x@example.com"}, selected.SERVICES[0])
    aggregate = adapter.result([row])
    merged = _merge_registration_services({"services": []}, aggregate)
    assert merged["services"][0]["kind"] == "registration"
    assert aggregate["checked"] == aggregate["found"] == 1
    assert "x@example.com" not in json.dumps(aggregate)


def test_worker_runs_selected_checks_when_holehe_is_unavailable(monkeypatch):
    real_client = httpx.AsyncClient
    requests = []
    def missing_module(name):
        raise ImportError("Optional runtime missing")
    def transport(request):
        requests.append(request)
        if request.url.host == "huggingface.co":
            return httpx.Response(200, json={"message": "This email address already exists"})
        return httpx.Response(200, json={"status": True})
    monkeypatch.setattr(worker.importlib, "import_module", missing_module)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        transport=httpx.MockTransport(transport), **kwargs))
    rows = trio.run(worker.run, "x@example.com", httpx, trio)
    assert len(requests) == 2
    selected_rows = {row["id"]: row for row in rows if row["id"] in {"huggingface", "hackerrank"}}
    assert selected_rows["huggingface"]["status"] == "found"
    assert selected_rows["hackerrank"]["status"] == "no_signal"
    assert len(rows) == 125
    assert "x@example.com" not in json.dumps(rows)
