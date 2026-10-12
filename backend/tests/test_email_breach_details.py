"""Exact-email historical fields, deduplication, truncation and secret exclusion."""
import pytest
from modules.email_breach_details import breach_details, normalize_breach_details
from modules.email_evidence import build_email_evidence

EMAIL = "fixture@example.com"


def test_aliases_keep_source_and_month_precision_without_secrets():
    record = {"email": EMAIL, "username": "old-handle", "first_name": "Example", "last_name": "Person", "password": "DO_NOT_FORWARD",
              "token": "DO_NOT_FORWARD", "source": {"name": "Example breach", "breach_date": "2019-04"}}
    data = normalize_breach_details({"success": True, "found": 2, "result": [record, record]}, EMAIL)
    assert len(data["records"]) == 1
    assert data["records"][0]["password_exposed"] is True
    assert "DO_NOT_FORWARD" not in str(data)
    report = build_email_evidence({"breach_details": data})
    assert report["identity"]["username"][0]["basis"] == "historical_breach"
    assert report["timeline"][0]["date_label"] == "Apr 2019"
    assert report["counts"]["public_profiles"] == report["counts"]["registration_signals"] == 0


def test_incomplete_or_wrong_email_rows_never_become_completed_negatives():
    r = normalize_breach_details({"success": True, "found": 1, "result": [{"email": "another@example.com", "source": {"name": "Example"}}]}, EMAIL)
    assert r["status"] == "partial" and r["checked"] is False
    assert r["records"] == []
    partial = normalize_breach_details({"success": True, "found": 101, "result": []}, EMAIL)
    assert partial["truncated"] is True and partial["status"] == "partial"


@pytest.mark.parametrize("body", [{}, {"success": False, "result": []}, {"success": True, "result": [], "found": True}, {"success": True, "result": {}, "found": 0}])
def test_invalid_contract_is_rejected(body):
    with pytest.raises(ValueError): normalize_breach_details(body, EMAIL)


def test_disabled_never_sends_query(monkeypatch):
    monkeypatch.delenv("LEAKCHECK_APIKEY", raising=False)
    monkeypatch.setattr("modules.email_breach_details.requests.get", lambda *a, **kw: pytest.fail("No request"))
    assert breach_details(EMAIL)["status"] == "unconfigured"


def test_key_stays_in_header_and_http_failure_preserves_unknown(monkeypatch):
    monkeypatch.setenv("LEAKCHECK_APIKEY", "test-key")
    monkeypatch.setenv("EMAIL_BREACH_DETAILS_ENABLED", "true")
    class Reply:
        status_code = 429
    def get(endpoint, **kwargs):
        assert endpoint.endswith("fixture%40example.com")
        assert kwargs["params"]["type"] == "email"
        assert kwargs["headers"]["X-API-Key"] == "test-key"
        assert "key" not in kwargs["params"]
        assert kwargs["allow_redirects"] is False
        return Reply()
    monkeypatch.setattr("modules.email_breach_details.requests.get", get)
    result = breach_details(EMAIL)
    assert result["status"] == "rate_limited" and result["checked"] is False
    assert "test-key" not in str(result)


def test_pro_positive_updates_aggregate_outcome_without_dropping_public_failure(monkeypatch):
    from services import email as service
    monkeypatch.setattr(service.EmailLookup, "scan", lambda *a, **kw: {"summary": {"breached": False, "breach_count": 0, "breach_coverage": {"sources": [{"name": "Public source", "status": "unavailable", "checked": False}]}}, "errors": []})
    monkeypatch.setattr(service, "enrich_email", lambda e: {"status": "unconfigured", "profiles": [], "registrations": []})
    monkeypatch.setattr(service, "breach_details", lambda e: {"status": "ok", "checked": True, "breached": True, "reported_rows": 1, "records": [{"name": "Example", "date": "2019-04", "username": "old-name", "source": "LeakCheck Pro"}]})
    result = service.scan_email(EMAIL, True)
    assert result["summary"]["breach_outcome"] == "found"
    assert result["summary"]["breach_status"] == "partial_unavailable"
    assert result["summary"]["breach_coverage"]["completed"] == 1
    assert result["summary"]["breach_count"] == 1
