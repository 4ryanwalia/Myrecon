import pytest
from core.validation import email, ValidationError
from modules.email_lookup import EmailLookup


@pytest.mark.parametrize("value", [".name@example.com", "name.@example.com", "na..me@example.com", "a" * 65 + "@example.com", "name@-example.com", "name@example..com"])
def test_invalid_syntax_is_rejected_before_lookup(value):
    with pytest.raises(ValidationError): email(value)


def test_plus_address_is_valid_but_does_not_prove_provider_support(monkeypatch):
    assert email("User+tag@Example.com") == "user+tag@example.com"
    monkeypatch.setattr("modules.email_lookup._doh_query", lambda *args: [{"value": "50 last.example.com."}, {"value": "5 first.example.com."}] + [{"value": f"{n} mx{n}.example.com."} for n in range(10, 16)])
    analysis = EmailLookup().analyze("user+tag@example.com")
    assert analysis["plus_addressing"] is True
    assert len(analysis["mx_records"]) == 8
    assert analysis["mx_records"][0] == {"priority": 5, "host": "first.example.com"}
    assert analysis["deliverable"] is None
    assert analysis["smtp"]["status"] == "not_checked"


def test_null_mx_is_rejected_and_missing_mx_does_not_prove_undeliverable(monkeypatch):
    monkeypatch.setattr("modules.email_lookup._doh_query", lambda *args: [{"value": "0 ."}])
    null = EmailLookup().analyze("fixture@example.com")
    assert null["deliverable"] is False and null["has_mx"] is False
    monkeypatch.setattr("modules.email_lookup._doh_query", lambda *args: [])
    assert EmailLookup().analyze("fixture@example.com")["deliverable"] is None
