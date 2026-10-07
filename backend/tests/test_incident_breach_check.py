import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from services import breach_check as service

TARGET = {"name": "Adobe", "breach_date": "2013-10-04"}
RECORD = {"breachID": "Adobe", "breachedDate": "2013-10-01", "searchable": True, "sensitive": False}

@pytest.mark.parametrize("rows", [[], [{**RECORD, "breachedDate": "2022-10-01"}],
    [{**RECORD, "searchable": False}], [{**RECORD, "sensitive": True}], [RECORD, RECORD]])
def test_uncovered_ambiguous_or_private_incident_does_not_query_email(monkeypatch, rows):
    monkeypatch.setattr(service, "catalogue", lambda: rows)
    monkeypatch.setattr(service, "_get_json", lambda url: pytest.fail("Email must not be sent"))
    assert service.check_incident("fixture@example.com", [TARGET])["state"] == "unsupported"

@pytest.mark.parametrize("payload,state", [
    ({"status": "success", "breaches": [["Adobe", "Unrelated"]]}, "found"),
    ({"status": "success", "breaches": [["Unrelated"]]}, "not_found"),
    ({"Error": "Not found"}, "not_found"), ({"Error": "Service unavailable"}, "unavailable"),
    ({}, "unavailable"), ({"status": "success", "breaches": [None]}, "unavailable"),
    ({"status": "success", "breaches": [[{}]]}, "unavailable"),
])
def test_results_are_scoped_and_malformed_bodies_fail_closed(monkeypatch, payload, state):
    monkeypatch.setattr(service, "catalogue", lambda: [RECORD])
    monkeypatch.setattr(service, "_get_json", lambda url: payload)
    result = service.check_incident("fixture@example.com", [TARGET])
    assert result["state"] == state
    assert "Unrelated" not in str(result)
    assert "fixture@example.com" not in str(result)

@pytest.mark.parametrize("reason,state", [("rate_limited", "rate_limited"), ("unavailable", "unavailable")])
def test_provider_failure_cannot_report_no_match(monkeypatch, reason, state):
    monkeypatch.setattr(service, "catalogue", lambda: [RECORD])
    def fail(url): raise RuntimeError(reason)
    monkeypatch.setattr(service, "_get_json", fail)
    assert service.check_incident("fixture@example.com", [TARGET])["state"] == state

def test_same_company_different_incident_does_not_match():
    assert service.resolve_target({**TARGET, "breach_date": "2022-10-04"}, [RECORD]) is None

def test_endpoint_validates_and_never_saves_history(monkeypatch):
    import app, config
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(service, "check_incident", lambda email, targets: {"state": "found", "message": "Selected breach only"})
    client = app.create_app().test_client()
    response = client.post('/api/breach-check', json={"email": "fixture@example.com", "targets": [TARGET]})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'history_id' not in response.json
    for bad in [None, {}, [{"name": "Adobe", "breach_date": "bad"}], [TARGET] * 4]:
        assert client.post('/api/breach-check', json={"email": "fixture@example.com", "targets": bad}).status_code == 422
