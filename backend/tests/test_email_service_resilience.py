"""An optional rich-source parser error must preserve completed evidence."""
import pytest

from services import email as service


@pytest.mark.parametrize("broken", ["profile", "breach"])
def test_optional_source_exception_retains_public_profile_and_breach(monkeypatch, broken):
    monkeypatch.setattr(service.EmailLookup, "scan", lambda *a, **k: {
        "query": {"email": "fixture@example.com"},
        "github": {"status": "found", "username": "example", "url": "https://github.com/example"},
        "breaches": {"status": "ok", "checked": True, "breached": True, "sources": [{"name": "Example incident", "date": "2020"}]},
        "summary": {"breached": True, "breach_count": 1},
    })
    def failed(email):
        raise RuntimeError("fixture@example.com PRIVATE_PROVIDER_TOKEN")
    monkeypatch.setattr(service, "enrich_email", failed if broken == "profile" else lambda e: {"status": "ok", "profiles": [], "registrations": [], "sources": []})
    monkeypatch.setattr(service, "breach_details", failed if broken == "breach" else lambda e: {"status": "unconfigured", "records": []})
    result = service.scan_email("fixture@example.com", True)
    assert result["partial"] is True
    assert result["evidence_report"]["profiles"][0]["username"] == "example"
    assert result["summary"]["breached"] is True
    assert result["evidence_report"]["counts"]["named_breaches"] == 1
    assert "PRIVATE_PROVIDER_TOKEN" not in str(result)
    assert "fixture@example.com" not in str(result["errors"])
