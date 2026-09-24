"""Mail spoofing verdicts from SPF and DMARC.

Offline: the grading is pure, so these feed it records directly. The case
worth pinning is that a verdict never reads "protected" unless a receiver is
actually told to act on every forged message — p=none, pct<100 and a broken
record all look configured at a glance and are not.

    python -m pytest backend/tests/test_mail_security.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.network import _dmarc_tags, _txt_value, mail_security  # noqa: E402


def _txt(*values):
    return [{"value": v, "ttl": 300} for v in values]


def _dmarc(*records, name="example.com", inherited=False):
    return {"name": name, "records": list(records), "inherited": inherited}


def test_txt_value_joins_quoted_strings_and_accepts_unquoted():
    assert _txt_value('"v=spf1 include:a.com " "include:b.com -all"') == "v=spf1 include:a.com include:b.com -all"
    assert _txt_value("v=spf1 -all") == "v=spf1 -all"


def test_enforcing_dmarc_is_protected():
    r = mail_security(_txt("v=spf1 include:_spf.google.com ~all"), _dmarc("v=DMARC1; p=reject; rua=mailto:d@example.com"))
    assert r["verdict"] == "protected"
    assert r["dmarc"]["policy"] == "reject" and r["dmarc"]["reports"]
    assert r["spf"]["all"] == "~all"
    assert r["issues"] == []


def test_enforcing_dmarc_without_spf_still_blocks_forgery():
    r = mail_security([], _dmarc("v=DMARC1; p=quarantine"))
    assert r["verdict"] == "protected"
    assert any("No SPF" in i for i in r["issues"])


def test_p_none_is_only_partial():
    r = mail_security(_txt("v=spf1 -all"), _dmarc("v=DMARC1; p=none"))
    assert r["verdict"] == "partial"
    assert any("p=none" in i for i in r["issues"])


def test_partial_pct_is_not_protected():
    r = mail_security(_txt("v=spf1 -all"), _dmarc("v=DMARC1; p=reject; pct=25"))
    assert r["verdict"] == "partial"
    assert r["dmarc"]["pct"] == 25


def test_spf_only_is_partial():
    assert mail_security(_txt("v=spf1 mx -all"), _dmarc())["verdict"] == "partial"


def test_nothing_published_is_exposed():
    r = mail_security(_txt("google-site-verification=abc"), _dmarc())
    assert r["verdict"] == "exposed"
    assert not r["spf"]["present"] and not r["dmarc"]["present"]


def test_plus_all_authorises_everyone():
    r = mail_security(_txt("v=spf1 +all"), _dmarc())
    assert r["verdict"] == "exposed"
    assert any("+all" in i for i in r["issues"])


def test_duplicate_spf_records_break_spf():
    r = mail_security(_txt("v=spf1 -all", "v=spf1 include:x.com -all"), _dmarc())
    assert not r["spf"]["valid"]
    assert r["verdict"] == "exposed"


def test_duplicate_dmarc_records_are_ignored_by_receivers():
    r = mail_security(_txt("v=spf1 -all"), _dmarc("v=DMARC1; p=reject", "v=DMARC1; p=none"))
    assert r["verdict"] == "partial"
    assert any("More than one DMARC" in i for i in r["issues"])


def test_redirect_is_not_flagged_as_missing_all():
    r = mail_security(_txt("v=spf1 redirect=_spf.example.com"), _dmarc("v=DMARC1; p=reject"))
    assert not any("closing all" in i for i in r["issues"])


def test_inherited_record_uses_subdomain_policy():
    r = mail_security([], _dmarc("v=DMARC1; p=reject; sp=none", inherited=True))
    assert r["dmarc"]["policy"] == "none"
    assert r["verdict"] == "partial"


def test_dmarc_tags_tolerate_spacing():
    assert _dmarc_tags("v=DMARC1 ;  p = quarantine ; pct=50")["p"] == "quarantine"
