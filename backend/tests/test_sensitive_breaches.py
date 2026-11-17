"""Sensitive breaches never appear in email results.

Anyone can type any address into the email tool. A breach that HIBP or
XposedOrNot flags as sensitive (adult and dating sites, political
correspondence, health services, stalkerware) reveals something private just
by being listed, so it is dropped from every source before anything is
counted. The note explaining that rule is constant, so its presence reveals
nothing about the address.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.email_breach_details import normalize_breach_details  # noqa: E402
from modules.email_lookup import EmailLookup  # noqa: E402
from modules.sensitive_breaches import POLICY_NOTE, is_sensitive  # noqa: E402

_JSON = {"Content-Type": "application/json"}


class _Resp:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or _JSON

    def json(self):
        return self._payload


def test_matcher_knows_sensitive_names_and_spares_ordinary_ones():
    for name in ("AdultFriendFinder.com", "Ashley Madison", "AshleyMadison", "Hjedd", "Medela"):
        assert is_sensitive(name), name
    for name in ("Adobe", "Canva.com", "LinkedIn", "Dropbox", "NetEase", "163.com"):
        assert not is_sensitive(name), name


def test_keyword_rule_catches_uncatalogued_adult_and_dating_names():
    for name in ("Sexclub.ru", "DatingFactory", "ChristianDating", "free-dating.ru", "xxxcams.net"):
        assert is_sensitive(name), name
    # Place names and ordinary words that contain the same letters.
    for name in ("Essex Police", "Sussex", "Middlesex", "Updating.com", "Validating", "Veterans Affairs"):
        assert not is_sensitive(name), name


def test_leakcheck_sources_drop_sensitive_names(monkeypatch):
    payload = {"success": True, "found": 7, "fields": ["password"],
               "sources": [{"name": "AdultFriendFinder.com", "date": "2016-10"},
                           {"name": "Canva.com", "date": "2019-05"}]}
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: _Resp(200, payload))
    result = EmailLookup().breaches("someone@example.com")
    assert [s["name"] for s in result["sources"]] == ["Canva.com"]
    assert result["breached"] is True


def test_leakcheck_with_only_sensitive_sources_reads_as_no_listed_breach(monkeypatch):
    payload = {"success": True, "found": 3, "fields": ["password", "dob"],
               "sources": [{"name": "Ashley Madison", "date": "2015-07"}]}
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: _Resp(200, payload))
    result = EmailLookup().breaches("someone@example.com")
    assert result["sources"] == [] and result["count"] == 0 and result["fields"] == []
    assert result["breached"] is False
    assert result["checked"] is True  # it was a real answer, not an outage


def test_xposedornot_fallback_drops_sensitive_names(monkeypatch):
    payload = {"breaches": [["Hjedd", "Adobe"]], "status": "success"}
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: _Resp(200, payload))
    result = EmailLookup().xposed_check_email("someone@example.com")
    assert [s["name"] for s in result["sources"]] == ["Adobe"]
    assert result["count"] == 1


def test_breach_analytics_drops_sensitive_rows_and_their_metrics(monkeypatch):
    payload = {
        "ExposedBreaches": {"breaches_details": [
            {"breach": "Medela", "domain": "medela.com", "xposed_date": "2026", "xposed_records": 400000,
             "xposed_data": "Email addresses;Support tickets"},
            {"breach": "Adobe", "domain": "adobe.com", "xposed_date": "2013", "xposed_records": 150000000,
             "xposed_data": "Email addresses;Passwords"},
        ]},
        "BreachMetrics": {"risk": [{"risk_label": "High", "risk_score": 9}],
                          "yearwise_details": [{"y2013": 1, "y2026": 1}]},
    }
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: _Resp(200, payload))
    result = EmailLookup().darkweb("someone@example.com")
    assert [b["name"] for b in result["breaches"]] == ["Adobe"]
    assert result["count"] == 1 and result["records_exposed"] == 150000000
    assert result["timeline"] == [{"year": 2013, "count": 1}]  # no 2026 bar from the hidden row
    assert {d["name"] for d in result["exposed_data"]} == {"Email addresses", "Passwords"}


def test_breach_analytics_with_only_sensitive_rows_is_a_clean_answer(monkeypatch):
    payload = {"ExposedBreaches": {"breaches_details": [
        {"breach": "AdultFriendFinder", "domain": "adultfriendfinder.com", "xposed_date": "2016"}]},
        "BreachMetrics": {}}
    monkeypatch.setattr("modules.email_lookup.requests.get", lambda *a, **k: _Resp(200, payload))
    result = EmailLookup().darkweb("someone@example.com")
    assert result["checked"] is True and result["breached"] is False and result["breaches"] == []


def test_leakcheck_pro_details_drop_sensitive_rows():
    payload = {"success": True, "found": 2, "result": [
        {"email": "a@example.com", "source": {"name": "Ashley Madison", "breach_date": "2015-07"}},
        {"email": "a@example.com", "source": {"name": "Adobe", "breach_date": "2013-10"}},
    ]}
    result = normalize_breach_details(payload, "a@example.com")
    assert [r["name"] for r in result["records"]] == ["Adobe"]


def test_policy_note_is_constant_and_present_on_every_scan(monkeypatch):
    def fake_get(url, *a, **k):
        if "leakcheck" in url:
            return _Resp(200, {"success": True, "found": 0, "sources": []})
        if "breach-analytics" in url:
            return _Resp(200, {"ExposedBreaches": None})
        return _Resp(200, {})
    monkeypatch.setattr("modules.email_lookup.requests.get", fake_get)
    monkeypatch.setattr(EmailLookup, "analyze", lambda self, email: {"email": email, "domain": "example.com",
                                                                     "deliverable": None, "disposable": None})
    result = EmailLookup().scan("someone@example.com")
    assert result["summary"]["sensitive_policy"] == POLICY_NOTE
