"""The email tool's "linked services" list: evidence only, never a guess."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.email_lookup import _linked_services  # noqa: E402

NONE = {"exists": False}


def _names(result):
    return [r["service"] for r in result["services"]]


def test_breaches_become_services_and_merge_across_sources():
    out = _linked_services(
        NONE, None, NONE,
        {"sources": [{"name": "Canva.com", "date": "2019-05"}]},
        {"breaches": [{"name": "Canva", "domain": "canva.com", "date": "2019"},
                      {"name": "LinkedIn", "domain": "linkedin.com", "date": "2012"}]},
        {"sources": []},
    )
    assert _names(out) == ["Canva", "LinkedIn"]
    canva = out["services"][0]
    assert canva["kind"] == "breach" and canva["domain"] == "canva.com" and canva["date"] == "2019"
    assert out["from_breaches"] == 2


def test_compilations_are_counted_but_never_listed():
    out = _linked_services(
        NONE, None, NONE,
        {"sources": [{"name": "Stealer Logs"}, {"name": "Collection 1"},
                     {"name": "Combolists"}, {"name": "Dropbox"}]},
        {"breaches": [{"name": "AntiPublic"}, {"name": "Exploit.In"}]},
        {"sources": []},
    )
    assert _names(out) == ["Dropbox"]
    assert out["compilations_skipped"] == 5


def test_profiles_outrank_breaches_and_list_first():
    out = _linked_services(
        {"exists": True, "profile_url": "https://gravatar.com/x", "accounts": []},
        {"url": "https://github.com/x"}, {"exists": True},
        {"sources": [{"name": "GitHub", "date": "2020"}, {"name": "Adobe", "date": "2013"}]},
        {"breaches": []}, {"sources": []},
    )
    assert _names(out) == ["GitHub", "Gravatar", "OpenPGP key", "Adobe"]
    github = out["services"][0]
    assert github["kind"] == "profile" and github["url"] == "https://github.com/x"


def test_nothing_found_is_an_empty_list_not_an_error():
    out = _linked_services(NONE, None, NONE, {"sources": []}, {"breaches": []}, None)
    assert out == {"services": [], "count": 0, "from_breaches": 0,
                   "from_profiles": 0, "compilations_skipped": 0}


def test_breach_count_does_not_double_count_domain_style_names(monkeypatch):
    from modules import email_lookup as el

    lk = el.EmailLookup()
    monkeypatch.setattr(lk, "analyze", lambda e: {"deliverable": True, "disposable": False})
    monkeypatch.setattr(lk, "gravatar", lambda e: {"exists": False, "accounts": []})
    monkeypatch.setattr(lk, "github", lambda e: None)
    monkeypatch.setattr(lk, "pgp", lambda e: {"exists": False, "status": "ok"})
    monkeypatch.setattr(lk, "breaches", lambda e: {
        "status": "ok", "checked": True, "breached": True, "count": 3,
        "sources": [{"name": "Canva.com"}, {"name": "GamingMonk"}, {"name": "GamingMonk.com"}]})
    monkeypatch.setattr(lk, "darkweb", lambda e: {
        "status": "ok", "checked": True, "breached": True, "count": 2, "records_exposed": 0,
        "risk_label": "", "risk_score": 0,
        "breaches": [{"name": "Canva"}, {"name": "GamingMonk"}]})
    out = lk.scan("a@example.com")
    assert out["summary"]["breach_count"] == 2
    assert out["summary"]["linked_services_count"] == 2
