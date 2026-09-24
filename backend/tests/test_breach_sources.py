"""Breach lookup: LeakCheck, the XposedOrNot fallback, and how failure is reported.

Two kinds of test live here and they are deliberately separated.

The offline ones use stub responses and always run. They pin the part that is
actually dangerous: that a rate limit or an outage can never be rendered as
"this address is clean". That is the answer people act on by doing nothing, so
it is the one that must not be reachable by accident.

The live ones call XposedOrNot for real. It needs no key, so unlike the Have I
Been Pwned checks these replaced, they run every time.

    python -m pytest backend/tests/test_breach_sources.py -k live -s
"""

import os
import sys
import pytest

# Same convention as the other backend tests: the package root is backend/,
# so its own `from modules.network import ...` imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.email_lookup import EmailLookup, _retry_after, _worst_status  # noqa: E402


class _Resp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


# LeakCheck's own JSON header, so the content-type guard does not reject it.
_LC_JSON = {"Content-Type": "application/json"}


# ── retry-after parsing ──────────────────────────────────────────

def test_retry_after_reads_the_header_in_either_casing():
    assert _retry_after(_Resp(429, headers={"retry-after": "2"})) == 2
    assert _retry_after(_Resp(429, headers={"Retry-After": "45"})) == 45


def test_retry_after_is_none_rather_than_a_guess():
    """A missing or unparseable header must not become a fabricated wait."""
    assert _retry_after(_Resp(429)) is None
    assert _retry_after(_Resp(429, headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})) is None
    assert _retry_after(_Resp(429, headers={"retry-after": ""})) is None


# ── LeakCheck failure modes ──────────────────────────────────────

def _intel_with(monkeypatch, response):
    intel = EmailLookup()
    monkeypatch.setattr(
        "modules.email_lookup.requests.get",
        lambda *a, **k: response,
    )
    return intel


def test_leakcheck_429_is_rate_limited_not_clean(monkeypatch):
    intel = _intel_with(monkeypatch, _Resp(429, headers={"retry-after": "1"}))
    out = intel.breaches("someone@example.com")
    assert out["status"] == "rate_limited"
    assert out["retry_after"] == 1
    # The load-bearing assertion: a throttled lookup has not checked anything.
    assert out["checked"] is False
    assert out["breached"] is False


def test_leakcheck_5xx_is_unavailable_not_clean(monkeypatch):
    intel = _intel_with(monkeypatch, _Resp(503))
    out = intel.breaches("someone@example.com")
    assert out["status"] == "unavailable"
    assert out["checked"] is False


def test_leakcheck_transport_failure_is_unavailable(monkeypatch):
    import requests as _requests

    def boom(*a, **k):
        raise _requests.RequestException("no route to host")

    intel = EmailLookup()
    monkeypatch.setattr("modules.email_lookup.requests.get", boom)
    out = intel.breaches("someone@example.com")
    assert out["status"] == "unavailable"
    assert out["checked"] is False


def test_leakcheck_200_with_no_hit_is_a_real_negative(monkeypatch):
    intel = _intel_with(monkeypatch, _Resp(200, {"success": False}))
    out = intel.breaches("someone@example.com")
    assert out["status"] == "ok"
    assert out["checked"] is True
    assert out["breached"] is False


# ── XposedOrNot check-email failure modes ────────────────────────
#
# Contract read off the live endpoint, not assumed:
#   found   200 {"breaches": [["Adobe", "Dropbox"]], "status": "success"}
#   clean   200 {"Error": "Not found", "email": null}
#   blocked 200 text/html  (Cloudflare interstitial)

_JSON = {"Content-Type": "application/json"}


def test_xon_flattens_the_nested_breach_array(monkeypatch):
    """`breaches` is a list CONTAINING a list. Missing that yields zero hits."""
    intel = _intel_with(
        monkeypatch,
        _Resp(200, {"breaches": [["Adobe", "Dropbox", "LinkedIn"]],
                    "email": "a@b.com", "status": "success"}, _JSON),
    )
    out = intel.xposed_check_email("a@b.com")
    assert out["status"] == "ok"
    assert out["breached"] is True
    assert out["count"] == 3
    assert [x["name"] for x in out["sources"]] == ["Adobe", "Dropbox", "LinkedIn"]


def test_xon_not_found_is_clean_despite_saying_Error(monkeypatch):
    """The trap: a clean address answers 200 with the word Error in the body.

    Reading that as a failure would turn every unbreached address into "we
    could not check", which is the same lie as the reverse.
    """
    intel = _intel_with(monkeypatch, _Resp(200, {"Error": "Not found", "email": None}, _JSON))
    out = intel.xposed_check_email("nobody@example.com")
    assert out["status"] == "ok"
    assert out["breached"] is False
    assert out["count"] == 0


def test_xon_deduplicates_names(monkeypatch):
    intel = _intel_with(
        monkeypatch,
        _Resp(200, {"breaches": [["Adobe", "adobe", "ADOBE", "Dropbox"]]}, _JSON),
    )
    out = intel.xposed_check_email("a@b.com")
    assert out["count"] == 2


def test_xon_challenge_page_is_unavailable_not_clean(monkeypatch):
    """A Cloudflare interstitial is served as HTML with a 200."""
    intel = _intel_with(monkeypatch, _Resp(200, None, {"Content-Type": "text/html"}))
    out = intel.xposed_check_email("a@b.com")
    assert out["status"] == "unavailable"
    assert out["breached"] is False


def test_xon_429_is_rate_limited(monkeypatch):
    intel = _intel_with(monkeypatch, _Resp(429, None, {"retry-after": "5"}))
    out = intel.xposed_check_email("a@b.com")
    assert out["status"] == "rate_limited"
    assert out["retry_after"] == 5


def test_xon_5xx_is_unavailable(monkeypatch):
    intel = _intel_with(monkeypatch, _Resp(503, None, _JSON))
    out = intel.xposed_check_email("a@b.com")
    assert out["status"] == "unavailable"


def test_xon_transport_failure_is_unavailable(monkeypatch):
    import requests as _requests

    def boom(*a, **k):
        raise _requests.RequestException("no route")

    intel = EmailLookup()
    monkeypatch.setattr("modules.email_lookup.requests.get", boom)
    out = intel.xposed_check_email("a@b.com")
    assert out["status"] == "unavailable"


# ── How the two combine ──────────────────────────────────────────

def test_worst_status_flags_a_clean_looking_but_unchecked_result():
    # LeakCheck throttled, fallback answered, nothing found: there IS a gap
    # behind this result and the client must be told.
    assert _worst_status({"status": "rate_limited"}, {"status": "ok"}, {}) == "partial_rate_limited"


def test_worst_status_is_ok_when_everything_answered():
    assert _worst_status({"status": "ok"}, {"status": "skipped"}, {}) == "ok"


def test_worst_status_reports_total_failure_distinctly():
    assert _worst_status({"status": "unavailable"}, None, {"error": "down"}) == "unavailable"


def test_fallback_is_not_called_when_leakcheck_answered(monkeypatch):
    """The fallback is a fallback, not a second request made every time."""
    calls = []

    intel = EmailLookup()
    monkeypatch.setattr(intel, "analyze", lambda e: {"deliverable": True, "disposable": False})
    monkeypatch.setattr(intel, "gravatar", lambda e: {"exists": False, "accounts": []})
    monkeypatch.setattr(intel, "github", lambda e: None)
    monkeypatch.setattr(
        intel, "darkweb",
        lambda e: {"breached": False, "breaches": [], "count": 0, "records_exposed": 0,
                   "risk_label": "", "risk_score": 0},
    )
    monkeypatch.setattr(intel, "breaches", lambda e: {"status": "ok", "breached": False,
                                                      "count": 0, "sources": [], "checked": True})
    monkeypatch.setattr(intel, "xposed_check_email",
                        lambda e: calls.append(e) or {"status": "ok"})

    out = intel.scan("someone@example.com")
    assert calls == [], "the fallback ran even though LeakCheck answered"
    assert out["fallback"]["status"] == "skipped"
    assert out["summary"]["breach_status"] == "ok"


def test_fallback_is_called_when_leakcheck_is_rate_limited(monkeypatch):
    calls = []

    intel = EmailLookup()
    monkeypatch.setattr(intel, "analyze", lambda e: {"deliverable": True, "disposable": False})
    monkeypatch.setattr(intel, "gravatar", lambda e: {"exists": False, "accounts": []})
    monkeypatch.setattr(intel, "github", lambda e: None)
    monkeypatch.setattr(
        intel, "darkweb",
        lambda e: {"breached": False, "breaches": [], "count": 0, "records_exposed": 0,
                   "risk_label": "", "risk_score": 0},
    )
    monkeypatch.setattr(intel, "breaches", lambda e: {"status": "rate_limited", "breached": False,
                                                      "count": 0, "sources": [], "checked": False,
                                                      "retry_after": 1})

    def fake_fallback(e):
        calls.append(e)
        return {"status": "ok", "breached": True, "count": 1,
                "sources": [{"name": "Adobe", "date": ""}]}

    monkeypatch.setattr(intel, "xposed_check_email", fake_fallback)

    out = intel.scan("someone@example.com")
    assert calls == ["someone@example.com"], "the fallback did not cover for LeakCheck"
    assert out["summary"]["breached"] is True
    assert out["summary"]["breach_count"] == 1


# ── Live XposedOrNot ─────────────────────────────────────────────
#
# No key, so these always run. Addresses are generic role accounts on
# example.com rather than anyone's real mailbox.

def test_live_xon_known_breached_address_returns_names():
    intel = EmailLookup()
    out = intel.xposed_check_email("info@example.com")
    print(f"\ninfo@example.com -> {out['status']} breached={out['breached']} "
          f"count={out['count']}")
    if out["status"] != "ok":
        pytest.skip(f"XposedOrNot did not answer: {out.get('error')}")
    assert out["breached"] is True
    assert out["count"] > 0
    assert all(src["name"] for src in out["sources"]), "a breach came back unnamed"


def test_live_xon_unknown_address_is_a_real_negative():
    intel = EmailLookup()
    out = intel.xposed_check_email("qhvrelbunsta-zzq7x@example.com")
    print(f"\nunknown -> {out['status']} breached={out['breached']}")
    if out["status"] != "ok":
        pytest.skip(f"XposedOrNot did not answer: {out.get('error')}")
    assert out["breached"] is False
    assert out["count"] == 0
