"""Accounts, plans and billing: who may scan, how often, and who gets paid-for passes.

Everything runs against the in-memory store and a locally generated RSA key,
so nothing here needs Firebase or Razorpay. Each test pins a rule that would
cost either the user (a scan wrongly refused, a paid pass not applied) or the
site (a pass applied twice, or to the wrong account) if it regressed.
"""
import hashlib
import hmac
import json
import os
import sys
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import config  # noqa: E402
from core import firebase_auth, plans, razorpay, store  # noqa: E402

PROJECT = config.FIREBASE_PROJECT_ID
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(uid="user-1", email="a@example.com", **over):
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT,
        "sub": uid, "email": email, "name": "Test", "iat": now - 5,
        "auth_time": now - 5, "exp": now + 3600,
    }
    claims.update(over)
    return jwt.encode(claims, _KEY, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(firebase_auth, "_public_keys", lambda force=False: {"k1": _KEY.public_key()})
    mem = store._MemoryStore()
    monkeypatch.setattr(store, "store", mem)
    monkeypatch.setattr(plans, "store", mem)
    monkeypatch.setattr(store, "persistent", lambda: True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "CACHE_ENABLED", False)
    import services.search as search
    fake = {"status": "ok", "query": {}, "summary": {}, "results": {}}
    monkeypatch.setattr(search, "_run_username", lambda *a, **k: fake)
    monkeypatch.setattr(search, "_run_full", lambda *a, **k: {**fake, "scope": "full"})
    monkeypatch.setattr(app_module, "_cache", app_module.TTLCache())
    yield


@pytest.fixture
def client():
    return app_module.app.test_client()


def _scan(client, token=None, scope="standard", ip="8.8.8.8"):
    headers = {"Content-Type": "application/json", "X-Forwarded-For": ip}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/api/username", data=json.dumps({"username": "octocat", "deep": True,
                                                         "scope": scope}), headers=headers)


# ── tokens ──────────────────────────────────────────────────────

def test_valid_token_is_accepted():
    assert firebase_auth.verify_id_token(_token())["sub"] == "user-1"


@pytest.mark.parametrize("over", [
    {"aud": "some-other-project"},
    {"iss": "https://securetoken.google.com/some-other-project"},
    {"exp": int(time.time()) - 3600},
    {"sub": ""},
])
def test_bad_tokens_are_refused(over):
    with pytest.raises(firebase_auth.AuthError):
        firebase_auth.verify_id_token(_token(**over))


def test_token_signed_by_another_key_is_refused():
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({"sub": "x", "aud": PROJECT}, other, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(firebase_auth.AuthError):
        firebase_auth.verify_id_token(forged)


def test_bad_token_is_401_not_a_silent_guest_scan(client):
    assert _scan(client, token="not-a-jwt").status_code == 401


# ── guests ──────────────────────────────────────────────────────

def test_guest_gets_five_standard_scans_a_day(client):
    codes = [_scan(client).status_code for _ in range(plans.GUEST_SCANS_PER_DAY + 1)]
    assert codes[:-1] == [200] * plans.GUEST_SCANS_PER_DAY
    assert codes[-1] == 429
    assert _scan(client).get_json()["code"] == "guest_limit"


def test_guest_limit_is_per_address(client):
    for _ in range(plans.GUEST_SCANS_PER_DAY):
        _scan(client, ip="8.8.8.8")
    assert _scan(client, ip="1.1.1.1").status_code == 200


def test_signed_in_standard_scans_are_not_metered(client):
    for _ in range(plans.GUEST_SCANS_PER_DAY + 3):
        assert _scan(client, token=_token()).status_code == 200


def test_guest_cannot_run_full_scan(client):
    r = _scan(client, scope="full")
    assert r.status_code == 401 and r.get_json()["code"] == "sign_in_required"


def test_full_scan_off_without_a_persistent_store(client, monkeypatch):
    monkeypatch.setattr(store, "persistent", lambda: False)
    assert _scan(client, token=_token(), scope="full").get_json()["code"] == "accounts_unavailable"


# ── free and pro allowances ─────────────────────────────────────

def test_free_account_gets_one_pro_scan_ever(client):
    t = _token()
    assert [_scan(client, t, "full").status_code for _ in range(2)] == [200, 402]
    body = _scan(client, t, "full").get_json()
    assert body["code"] == "upgrade_required"
    assert body["account"]["full_scans_left"] == 0


def test_failed_full_scan_is_refunded(monkeypatch, client):
    import services.search as search

    def boom(*a, **k):
        raise RuntimeError("sweep died")
    monkeypatch.setattr(search, "_run_full", boom)
    app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
    assert _scan(client, _token(), "full").status_code == 500
    assert plans.get_account("user-1")["free_scans_left"] == plans.FREE_FULL_SCANS


def test_pass_is_applied_once_per_order():
    assert plans.grant_pass("u", "weekly", "order_A") is True
    assert plans.grant_pass("u", "weekly", "order_A") is False  # webhook after verify
    acct = plans.get_account("u")
    assert acct["tier"] == "pro" and acct["pro_scans_left"] == 50


def test_passes_stack():
    plans.grant_pass("u", "weekly", "order_A")
    first_until = plans.get_account("u")["pro_until"]
    plans.grant_pass("u", "monthly", "order_B")
    acct = plans.get_account("u")
    assert acct["pro_scans_left"] == 250
    assert acct["pro_until"] - first_until == 30 * 86_400_000
    assert acct["plan"] == "monthly"


def test_pro_scans_are_spent_before_free_ones():
    plans.grant_pass("u", "weekly", "order_A")
    assert plans.consume_full_scan("u") == "pro"
    acct = plans.get_account("u")
    assert acct["pro_scans_left"] == 49 and acct["free_scans_left"] == 1


def test_expired_pass_falls_back_to_free():
    plans.grant_pass("u", "weekly", "order_A")
    rec = store.store.get("web/users/u")
    rec["pro"]["until"] = 1
    store.store.transaction("web/users/u", lambda _: rec)
    acct = plans.get_account("u")
    assert acct["tier"] == "free" and acct["full_scans_left"] == 1


# ── billing ─────────────────────────────────────────────────────

def _paid_order(uid="user-1", plan="weekly", status="paid", paid=9900):
    return {"id": "order_X", "status": status, "amount_paid": paid,
            "notes": {"uid": uid, "plan": plan}}


def _sig(secret, msg):
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", "whsec")


def _verify(client, token, sig=None):
    body = {"razorpay_order_id": "order_X", "razorpay_payment_id": "pay_1",
            "razorpay_signature": sig or _sig("secret", b"order_X|pay_1")}
    return client.post("/api/billing/verify", data=json.dumps(body), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}"})


def test_verify_applies_the_pass(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order())
    r = _verify(client, _token()).get_json()
    assert r["applied"] is True and r["account"]["pro_scans_left"] == 50


def test_verify_rejects_a_forged_signature(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order())
    assert _verify(client, _token(), sig="0" * 64).status_code == 400
    assert plans.get_account("user-1")["tier"] == "free"


def test_someone_elses_order_is_not_applied_to_me(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order(uid="someone-else"))
    assert _verify(client, _token()).get_json()["applied"] is False
    assert plans.get_account("user-1")["tier"] == "free"


def test_underpaid_or_unpaid_orders_are_not_applied(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order(paid=100))
    assert _verify(client, _token()).get_json()["applied"] is False
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order(status="attempted"))
    assert _verify(client, _token()).get_json()["applied"] is False


def test_webhook_needs_a_valid_signature(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order())
    raw = json.dumps({"event": "order.paid",
                      "payload": {"order": {"entity": {"id": "order_X"}}}}).encode()
    bad = client.post("/api/billing/webhook", data=raw, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": "nope"})
    assert bad.status_code == 400 and plans.get_account("user-1")["tier"] == "free"
    good = client.post("/api/billing/webhook", data=raw, headers={
        "Content-Type": "application/json", "X-Razorpay-Signature": _sig("whsec", raw)})
    assert good.status_code == 200 and plans.get_account("user-1")["tier"] == "pro"
    # ...and the browser's verify arriving afterwards does not apply it twice.
    _verify(client, _token())
    assert plans.get_account("user-1")["pro_scans_left"] == 50


def test_plans_endpoint_never_exposes_secrets(client, keys):
    body = client.get("/api/plans").get_data(as_text=True)
    assert "secret" not in body and "whsec" not in body
    assert "rzp_test_x" in body


def test_cors_allows_the_authorization_header(client, monkeypatch):
    monkeypatch.setattr(config, "CORS_ALLOW_ANY", True)
    r = client.options("/api/username", headers={"Origin": "https://myrecon.xyz"})
    assert "Authorization" in r.headers.get("Access-Control-Allow-Headers", "")


# ── sweep safety ────────────────────────────────────────────────

def test_handle_cannot_steer_a_subdomain_request():
    from modules.sweep import Sweep, CATALOGUE
    tumblr = next(p for p in CATALOGUE if p["name"] == "Tumblr")
    hit = Sweep("user@169.254.169.254").probe(tumblr)
    assert hit["verdict"] == "unknown" and hit["reason_code"] == "invalid_handle"


def test_stream_refuses_before_streaming(client):
    r = client.post("/api/username/stream", data=json.dumps({"username": "octocat", "scope": "full"}),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 401 and r.get_json()["code"] == "sign_in_required"


def test_verify_rejects_missing_fields(client, keys):
    r = client.post("/api/billing/verify", data=json.dumps({"razorpay_order_id": "order_X"}),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token()}"})
    assert r.status_code == 400 and r.get_json()["code"] == "payment_fields_missing"


def test_bad_razorpay_keys_are_a_401_not_a_crash(client, keys, monkeypatch):
    def refuse(*a, **k):
        raise razorpay.RazorpayAuthError("authentication failed")
    monkeypatch.setattr(razorpay, "create_order", refuse)
    r = client.post("/api/billing/order", data=json.dumps({"plan": "weekly"}),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token()}"})
    assert r.status_code == 401 and r.get_json()["code"] == "razorpay_auth_failed"


def test_dev_test_account_is_forced_off_in_production():
    # config.py computes it as (not IS_PRODUCTION) and the flag; the test
    # suite runs with FLASK_ENV unset, i.e. production.
    assert config.IS_PRODUCTION and config.DEV_TEST_ACCOUNT is False


def test_plans_serve_the_web_signin_config_only_when_set(client, monkeypatch):
    monkeypatch.setattr(config, "FIREBASE_WEB_API_KEY", "")
    assert client.get("/api/plans").get_json()["firebase"] is None
    monkeypatch.setattr(config, "FIREBASE_WEB_API_KEY", "public-web-key")
    fb = client.get("/api/plans").get_json()["firebase"]
    assert fb["apiKey"] == "public-web-key" and fb["projectId"] == config.FIREBASE_PROJECT_ID


# ── scan history ────────────────────────────────────────────────

def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_signed_in_scans_are_saved_and_reopened(client):
    t = _token()
    r = _scan(client, t).get_json()
    assert r["history_id"]
    scans = client.get("/api/history", headers=_auth(t)).get_json()["scans"]
    assert len(scans) == 1 and scans[0]["id"] == r["history_id"]
    one = client.get(f"/api/history/{r['history_id']}", headers=_auth(t)).get_json()["scan"]
    assert one["status"] == "ok" and one["rejected"] == []


def test_guest_scans_are_not_saved(client):
    assert _scan(client).get_json()["history_id"] is None


def test_history_is_private_to_its_owner(client):
    mine = _scan(client, _token(uid="alice")).get_json()["history_id"]
    bob = _token(uid="bob")
    assert client.get("/api/history", headers=_auth(bob)).get_json()["scans"] == []
    assert client.get(f"/api/history/{mine}", headers=_auth(bob)).status_code == 404


def test_history_needs_sign_in(client):
    assert client.get("/api/history").status_code == 401


def test_history_keeps_only_the_newest(client, monkeypatch):
    from core import history
    monkeypatch.setattr(history, "MAX_SCANS", 3)
    t = _token()
    ids = [_scan(client, t).get_json()["history_id"] for _ in range(5)]
    kept = [s["id"] for s in client.get("/api/history", headers=_auth(t)).get_json()["scans"]]
    assert sorted(kept) == sorted(ids[-3:])
    assert client.get(f"/api/history/{ids[0]}", headers=_auth(t)).status_code == 404


def test_history_delete_one_and_all(client):
    t = _token()
    a = _scan(client, t).get_json()["history_id"]
    _scan(client, t)
    assert client.delete(f"/api/history/{a}", headers=_auth(t)).status_code == 200
    assert len(client.get("/api/history", headers=_auth(t)).get_json()["scans"]) == 1
    client.delete("/api/history", headers=_auth(t))
    assert client.get("/api/history", headers=_auth(t)).get_json()["scans"] == []


def test_history_id_is_validated(client):
    assert client.get("/api/history/..%2F..%2Fusers", headers=_auth(_token())).status_code == 404
