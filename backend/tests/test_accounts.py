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


def test_paid_standard_scans_are_not_metered(client):
    plans.grant_pass("user-1", "extended", "order_paid")
    for _ in range(plans.GUEST_SCANS_PER_DAY + 3):
        assert _scan(client, token=_token()).status_code == 200




def _full_result():
    from modules.sweep import CATALOGUE
    visible, hidden = CATALOGUE[0]["name"], CATALOGUE[100]["name"]
    return {
        "status": "ok",
        "query": {"username": "octocat", "deep": True, "scope": "full"},
        "summary": {"total": 2, "profiles": 2, "checked": 560, "clusters": 1},
        "coverage": {"total": 560, "found": 2, "not_found": 558},
        "results": {"profiles": [
            {"platform": visible, "url": "https://visible.example/octocat", "exists": True},
            {"platform": hidden, "url": "https://hidden.example/octocat", "exists": True},
        ], "documents": [], "mentions": []},
        "identity_clusters": [{"profiles": [{"url": "https://hidden.example/octocat"}]}],
        "exposures": [{"url": "https://hidden.example/octocat"}],
        "rejected": [{"platform": visible, "url": "https://visible.example/other"},
                     {"platform": hidden, "url": "https://hidden.example/other"}],
        "unverified": [{"platform": hidden, "url": "https://hidden.example/unknown"}],
    }








def test_signed_in_daily_limit_requires_persistent_storage(client, monkeypatch):
    monkeypatch.setattr(store, "persistent", lambda: False)
    assert _scan(client, token=_token(), scope="full").get_json()["code"] == "accounts_unavailable"
    assert _scan(client, token=_token(), scope="extended").get_json()["code"] == "accounts_unavailable"


# ── free and pro allowances ─────────────────────────────────────

def test_free_account_gets_five_complete_standard_reports_daily(client):
    t = _token()
    # Old exhausted trial records must not restrict the newly free scans.
    store.store.transaction("web/users/user-1", lambda _: {"free": {"used_total": 999}})
    for _ in range(5):
        r = _scan(client, t, "full")
        assert r.status_code == 200 and "preview" not in r.get_json()
    r = _scan(client, t, "full")
    assert r.status_code == 429 and r.get_json()["code"] == "standard_daily_limit"
    assert r.get_json()["account"]["standard_scans_left"] == 0
    assert plans.get_account("user-1")["full_scans_unlimited"] is False
    assert store.store.get("web/users/user-1")["free"]["used_total"] == 999


def test_failed_free_full_scan_does_not_spend_extended_credits(monkeypatch, client):
    import services.search as search

    def boom(*a, **k):
        raise RuntimeError("sweep died")
    monkeypatch.setattr(search, "_run_full", boom)
    plans.grant_pass("user-1", "extended", "order_A")
    app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
    assert _scan(client, _token(), "full").status_code == 500
    assert plans.get_account("user-1")["extended_scans_left"] == 10


def test_pass_is_applied_once_per_order():
    assert plans.grant_pass("u", "weekly", "order_A") is True
    assert plans.grant_pass("u", "weekly", "order_A") is False  # webhook after verify
    acct = plans.get_account("u")
    assert acct["tier"] == "pro" and acct["pro_scans_left"] == 10


def test_payment_retry_grants_pass_if_user_write_failed(monkeypatch):
    original = store.store.transaction
    failed = {"value": False}

    def fail_user_write_once(path, fn, retries=10):
        if path == "web/users/u" and not failed["value"]:
            failed["value"] = True
            raise RuntimeError("temporary database failure")
        return original(path, fn)

    monkeypatch.setattr(store.store, "transaction", fail_user_write_once)
    with pytest.raises(RuntimeError, match="temporary database failure"):
        plans.grant_pass("u", "weekly", "order_retry_user")

    # No processed-payment claim was committed before the entitlement write.
    assert plans.grant_pass("u", "weekly", "order_retry_user") is True
    assert plans.get_account("u")["pro_scans_left"] == 10


def test_payment_retry_does_not_grant_pass_twice_if_ledger_write_failed(monkeypatch):
    ref = "order_retry_ledger"
    ref_key = hashlib.sha256(ref.encode()).hexdigest()[:40]
    payment_path = f"web/payments/{ref_key}"
    original = store.store.transaction
    failed = {"value": False}

    def fail_ledger_write_once(path, fn, retries=10):
        if path == payment_path and not failed["value"]:
            failed["value"] = True
            raise RuntimeError("temporary ledger failure")
        return original(path, fn)

    monkeypatch.setattr(store.store, "transaction", fail_ledger_write_once)
    with pytest.raises(RuntimeError, match="temporary ledger failure"):
        plans.grant_pass("u", "weekly", ref)
    assert plans.get_account("u")["pro_scans_left"] == 10

    assert plans.grant_pass("u", "weekly", ref) is True
    assert plans.get_account("u")["pro_scans_left"] == 10
    assert store.store.get(payment_path)["ref"] == ref


def test_passes_stack():
    plans.grant_pass("u", "weekly", "order_A")
    first_until = plans.get_account("u")["pro_until"]
    plans.grant_pass("u", "monthly", "order_B")
    acct = plans.get_account("u")
    assert acct["pro_scans_left"] == 60
    assert acct["pro_until"] - first_until == 30 * 86_400_000
    assert acct["plan"] == "monthly"


def test_free_full_scans_leave_legacy_paid_allowances_unchanged(client):
    plans.grant_pass("u", "weekly", "order_A")
    assert _scan(client, _token(uid="u"), "full").status_code == 200
    acct = plans.get_account("u")
    assert acct["pro_scans_left"] == 10 and acct["extended_scans_left"] == 2
    assert acct["full_scans_unlimited"] is True


def test_expired_pass_falls_back_to_free():
    plans.grant_pass("u", "weekly", "order_A")
    rec = store.store.get("web/users/u")
    rec["pro"]["until"] = 1
    store.store.transaction("web/users/u", lambda _: rec)
    acct = plans.get_account("u")
    assert acct["tier"] == "free" and acct["full_scans_unlimited"] is False
    assert acct["standard_scans_left"] == 5
    assert acct["extended_scans_left"] == 0


def test_quick_and_full_cached_requests_share_one_daily_allowance(client, monkeypatch):
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    app_module._cache.set(app_module._cache_key("username_full", "octocat"), _full_result())
    t = _token()
    for scope in ("full", "standard", "full", "standard", "full"):
        assert _scan(client, t, scope).status_code == 200
    assert _scan(client, t, "standard").get_json()["code"] == "standard_daily_limit"
    r = client.post("/api/username/stream", json={"username": "octocat", "scope": "full"},
                    headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 429 and r.get_json()["code"] == "standard_daily_limit"
    # Reopening a saved report does not use or require a daily scan.
    scans = client.get("/api/history", headers={"Authorization": f"Bearer {t}"}).get_json()["scans"]
    assert client.get(f"/api/history/{scans[0]['id']}", headers={"Authorization": f"Bearer {t}"}).status_code == 200


def test_standard_daily_allowance_is_per_uid_not_address(client):
    for _ in range(5):
        assert _scan(client, _token(uid="alice"), "full").status_code == 200
    assert _scan(client, _token(uid="alice"), "full", ip="1.1.1.1").status_code == 429
    assert _scan(client, _token(uid="bob"), "full").status_code == 200


def test_standard_daily_allowance_resets_at_midnight_utc(monkeypatch):
    # 2026-09-30 23:59 UTC and the next midnight.
    now = {"ms": 1790812740000}
    monkeypatch.setattr(plans, "_now_ms", lambda: now["ms"])
    first_day = plans._standard_day(now["ms"])
    for _ in range(5):
        plans.consume_standard_scan("u")
    acct = plans.get_account("u")
    assert acct["standard_scans_left"] == 0
    reset = acct["standard_resets_at"]
    now["ms"] = reset - 1
    with pytest.raises(plans.StandardLimit):
        plans.consume_standard_scan("u")
    now["ms"] = reset
    assert plans.get_account("u")["standard_scans_left"] == 5
    plans.consume_standard_scan("u")
    assert plans._standard_day(now["ms"]) != first_day
    assert plans.get_account("u")["standard_scans_left"] == 4


def test_daily_allowance_is_atomic_under_concurrent_requests():
    from concurrent.futures import ThreadPoolExecutor

    def reserve(_):
        try:
            plans.consume_standard_scan("u")
            return True
        except plans.StandardLimit:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(reserve, range(16)))
    assert sum(accepted) == 5
    assert plans.get_account("u")["standard_scans_left"] == 0


def test_paid_standard_access_survives_spending_all_extended_credits(client):
    plans.grant_pass("user-1", "extended", "order_pack")
    for _ in range(10):
        plans.consume_extended_scan("user-1")
    acct = plans.get_account("user-1")
    assert acct["tier"] == "pro" and acct["standard_scans_unlimited"] is True
    assert acct["extended_scans_left"] == 0
    for _ in range(12):
        assert _scan(client, _token(), "full").status_code == 200
    assert _scan(client, _token(), "extended").status_code == 402


def test_buying_pack_removes_an_exhausted_daily_limit(client):
    t = _token()
    for _ in range(5):
        _scan(client, t, "full")
    assert _scan(client, t, "full").status_code == 429
    plans.grant_pass("user-1", "extended", "order_pack")
    for _ in range(7):
        assert _scan(client, t, "full").status_code == 200
    assert plans.get_account("user-1")["extended_scans_left"] == 10


@pytest.mark.parametrize("scope", ["standard", "full"])
def test_failed_free_username_scan_refunds_daily_allowance(client, monkeypatch, scope):
    import services.search as search

    def boom(*args, **kwargs):
        raise RuntimeError("failed pipeline")

    monkeypatch.setattr(search, "_run_full" if scope == "full" else "_run_username", boom)
    assert _scan(client, _token(), scope).status_code == 500
    assert plans.get_account("user-1")["standard_scans_left"] == 5


def test_refund_for_yesterday_cannot_increase_todays_allowance(monkeypatch):
    now = {"ms": 1790812740000}
    monkeypatch.setattr(plans, "_now_ms", lambda: now["ms"])
    old_source = plans.consume_standard_scan("u")
    now["ms"] = plans.get_account("u")["standard_resets_at"]
    plans.consume_standard_scan("u")
    plans.refund_full_scan("u", old_source)
    assert plans.get_account("u")["standard_scans_left"] == 4


# ── extended allowance ──────────────────────────────────────────

def test_extended_requires_paid_credits_and_standard_stays_free(client):
    t = _token()
    body = _scan(client, t, "extended").get_json()
    assert body["code"] == "upgrade_required" and body["scope"] == "extended"
    assert _scan(client, t, "full").status_code == 200


def test_weekly_pass_gives_two_extended_scans_apart_from_full_ones(client):
    plans.grant_pass("user-1", "weekly", "order_A")
    t = _token()
    assert [_scan(client, t, "extended").status_code for _ in range(3)] == [200, 200, 402]
    acct = plans.get_account("user-1")
    assert acct["extended_scans_left"] == 0 and acct["pro_scans_left"] == 10


def test_monthly_pass_gives_six_extended_scans_and_passes_stack():
    plans.grant_pass("u", "monthly", "order_A")
    assert plans.get_account("u")["extended_scans_left"] == 6
    plans.grant_pass("u", "weekly", "order_B")
    assert plans.get_account("u")["extended_scans_left"] == 8


def test_pass_bought_before_extended_allowance_reads_its_plan_default():
    plans.grant_pass("u", "monthly", "order_A")
    rec = store.store.get("web/users/u")
    del rec["pro"]["extended_left"]
    store.store.transaction("web/users/u", lambda _: rec)
    assert plans.get_account("u")["extended_scans_left"] == 6
    assert plans.consume_extended_scan("u") == "extended"
    assert plans.get_account("u")["extended_scans_left"] == 5


def test_failed_extended_scan_is_refunded(monkeypatch, client):
    import services.search as search

    def boom(*a, **k):
        raise RuntimeError("sweep died")
    plans.grant_pass("user-1", "weekly", "order_A")
    monkeypatch.setattr(search, "_run_full", boom)
    app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
    assert _scan(client, _token(), "extended").status_code == 500
    assert plans.get_account("user-1")["extended_scans_left"] == 2


def test_pack_allows_ten_extended_scans_then_only_standard(client):
    plans.grant_pass("user-1", "extended", "order_pack")
    t = _token()
    for remaining in range(9, -1, -1):
        assert _scan(client, t, "extended").status_code == 200
        assert plans.get_account("user-1")["extended_pack_scans_left"] == remaining
    assert _scan(client, t, "extended").status_code == 402
    for _ in range(3):
        assert _scan(client, t, "full").status_code == 200


def test_pack_credits_stack_and_never_expire(monkeypatch):
    plans.grant_pass("u", "extended", "order_A")
    assert plans.consume_extended_scan("u") == "extended_pack"
    plans.grant_pass("u", "extended", "order_B")
    monkeypatch.setattr(plans, "_now_ms", lambda: 9_999_999_999_999)
    acct = plans.get_account("u")
    assert acct["plan"] == "extended" and acct["extended_scans_left"] == 19
    assert acct["pro_until"] is None


def test_pack_is_not_double_granted_after_ledger_failure(monkeypatch):
    ref = "order_pack_retry"
    ref_key = hashlib.sha256(ref.encode()).hexdigest()[:40]
    original = store.store.transaction
    failed = {"value": False}

    def fail_once(path, fn, retries=10):
        if path == f"web/payments/{ref_key}" and not failed["value"]:
            failed["value"] = True
            raise RuntimeError("temporary ledger failure")
        return original(path, fn)

    monkeypatch.setattr(store.store, "transaction", fail_once)
    with pytest.raises(RuntimeError):
        plans.grant_pass("u", "extended", ref)
    assert plans.grant_pass("u", "extended", ref) is True
    assert plans.get_account("u")["extended_scans_left"] == 10


def test_expiring_legacy_credits_are_spent_and_refunded_separately():
    plans.grant_pass("u", "weekly", "order_legacy")
    plans.grant_pass("u", "extended", "order_pack")
    source = plans.consume_extended_scan("u")
    assert source == "extended"
    acct = plans.get_account("u")
    assert acct["extended_legacy_scans_left"] == 1 and acct["extended_pack_scans_left"] == 10
    plans.refund_full_scan("u", source)
    assert plans.get_account("u")["extended_legacy_scans_left"] == 2
    plans.consume_extended_scan("u")
    plans.consume_extended_scan("u")
    source = plans.consume_extended_scan("u")
    assert source == "extended_pack"
    plans.refund_full_scan("u", source)
    assert plans.get_account("u")["extended_pack_scans_left"] == 10


def test_expired_legacy_pass_does_not_expire_pack_credits():
    plans.grant_pass("u", "weekly", "order_legacy")
    plans.grant_pass("u", "extended", "order_pack")
    rec = store.store.get("web/users/u")
    rec["pro"]["until"] = 1
    store.store.transaction("web/users/u", lambda _: rec)
    assert plans.get_account("u")["extended_scans_left"] == 10
    assert plans.consume_extended_scan("u") == "extended_pack"


def test_cached_extended_result_requires_credit_but_does_not_spend(client, monkeypatch):
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    app_module._cache.set(app_module._cache_key("username_extended", "octocat"), _full_result())
    t = _token()
    assert _scan(client, t, "extended").status_code == 402
    plans.grant_pass("user-1", "extended", "order_pack")
    assert _scan(client, t, "extended").status_code == 200
    assert plans.get_account("user-1")["extended_scans_left"] == 10
    for _ in range(10):
        plans.consume_extended_scan("user-1")
    assert _scan(client, t, "extended").status_code == 402


@pytest.mark.parametrize("stream", [False, True])
def test_guest_extended_cannot_leak_a_cached_result(client, monkeypatch, stream):
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    app_module._cache.set(app_module._cache_key("username_extended", "octocat"), _full_result())
    endpoint = "/api/username/stream" if stream else "/api/username"
    r = client.post(endpoint, json={"username": "octocat", "scope": "extended"})
    assert r.status_code == 401 and r.get_json()["code"] == "sign_in_required"
    assert "hidden.example" not in r.get_data(as_text=True)


def test_failed_extended_pack_scan_restores_one_credit(client, monkeypatch):
    import services.search as search
    plans.grant_pass("user-1", "extended", "order_pack")

    def boom(*args, **kwargs):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(search, "_run_full", boom)
    assert _scan(client, _token(), "extended").status_code == 500
    assert plans.get_account("user-1")["extended_scans_left"] == 10


@pytest.mark.parametrize("raises", [False, True])
def test_failed_extended_stream_restores_one_credit(client, monkeypatch, raises):
    import services.search as search
    plans.grant_pass("user-1", "extended", "order_pack")

    def events(*args, **kwargs):
        if raises:
            raise RuntimeError("stream failed")
        yield {"type": "error", "message": "stream failed"}

    monkeypatch.setattr(search, "stream_username", events)
    if raises:
        with pytest.raises(RuntimeError):
            client.post("/api/username/stream", json={"username": "octocat", "scope": "extended"},
                        headers={"Authorization": f"Bearer {_token()}"}, buffered=True)
    else:
        r = client.post("/api/username/stream", json={"username": "octocat", "scope": "extended"},
                        headers={"Authorization": f"Bearer {_token()}"}, buffered=True)
        assert '"type": "error"' in r.get_data(as_text=True)
    assert plans.get_account("user-1")["extended_scans_left"] == 10


# ── billing ─────────────────────────────────────────────────────

def _paid_order(uid="user-1", plan="extended", status="paid", paid=9900):
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
    assert r["applied"] is True and r["account"]["extended_pack_scans_left"] == 10


def test_only_one_pack_is_advertised_and_orders_cost_99_rupees(client, keys, monkeypatch):
    info = client.get("/api/plans").get_json()
    assert [p["id"] for p in info["plans"]] == ["extended"]
    assert info["plans"][0]["price_inr"] == 99
    assert info["plans"][0]["extended_scans"] == 10
    assert info["limits"]["free_standard_scans_per_day"] == 5
    assert info["limits"]["paid_standard_scans_unlimited"] is True
    calls = []
    monkeypatch.setattr(razorpay, "create_order", lambda amount, **kw: (
        calls.append({"amount": amount, **kw}),
        {"id": "order_new", "amount": amount, "currency": "INR"})[1])
    r = client.post("/api/billing/order", json={"plan": "extended", "amount": 1, "extended_scans": 100},
                    headers={"Authorization": f"Bearer {_token()}"})
    assert r.status_code == 200 and r.get_json()["amount"] == 9900
    assert calls[0]["amount"] == 9900
    for old in ("weekly", "monthly"):
        assert client.post("/api/billing/order", json={"plan": old},
                           headers={"Authorization": f"Bearer {_token()}"}).status_code == 422
    assert len(calls) == 1


def test_previously_created_legacy_orders_still_settle(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order(plan="monthly", paid=29900))
    r = _verify(client, _token()).get_json()
    assert r["applied"] is True and r["account"]["extended_legacy_scans_left"] == 6


def test_verification_retry_does_not_double_grant_pack(client, keys, monkeypatch):
    monkeypatch.setattr(razorpay, "fetch_order", lambda oid: _paid_order())
    assert _verify(client, _token()).get_json()["applied"] is True
    assert _verify(client, _token()).get_json()["applied"] is True
    assert plans.get_account("user-1")["extended_scans_left"] == 10


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
    assert plans.get_account("user-1")["extended_pack_scans_left"] == 10


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


def test_stream_rejects_bad_token_before_streaming(client):
    r = client.post("/api/username/stream", data=json.dumps({"username": "octocat", "scope": "full"}),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer bad"})
    assert r.status_code == 401 and r.get_json()["code"] == "auth_invalid"


def test_verify_rejects_missing_fields(client, keys):
    r = client.post("/api/billing/verify", data=json.dumps({"razorpay_order_id": "order_X"}),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token()}"})
    assert r.status_code == 400 and r.get_json()["code"] == "payment_fields_missing"


def test_bad_razorpay_keys_are_a_401_not_a_crash(client, keys, monkeypatch):
    def refuse(*a, **k):
        raise razorpay.RazorpayAuthError("authentication failed")
    monkeypatch.setattr(razorpay, "create_order", refuse)
    r = client.post("/api/billing/order", data=json.dumps({"plan": "extended"}),
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


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("cached", [False, True])
def test_guest_quick_exposes_two_cards_without_mutating_shared_cache(client, monkeypatch, stream, cached):
    import copy
    import services.search as search
    cards = [{"platform": name, "url": f"https://{name.lower()}.example/octocat",
              "category": "profile", "confidence": "high"}
             for name in ("First", "Second", "HiddenThird", "HiddenFourth")]
    full = {"status": "ok", "query": {"username": "octocat", "scope": "standard", "deep": True},
            "summary": {"total": 4, "profiles": 4, "checked": 100},
            "results": {"profiles": cards, "documents": [], "mentions": []},
            "identity_clusters": [{"profiles": cards}], "exposures": [{"url": cards[2]["url"]}],
            "platform_checks": cards, "user_scanner": {"hidden": cards[3]}}
    original = copy.deepcopy(full)
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    key = app_module._cache_key("username", "octocat", True)
    if cached:
        app_module._cache.set(key, full)
    monkeypatch.setattr(search, "_run_username", lambda *_args, **_kwargs: full)

    def events(*_args, **_kwargs):
        for card in cards:
            yield {"type": "progress", "phase": "Checking platforms", "percent": 20,
                   "detail": card["platform"] + ", found"}
            yield {"type": "found", "result": card}
        yield {"type": "found", "result": cards[0]}
        yield {"type": "complete", "data": full}

    monkeypatch.setattr(search, "stream_username", events)
    endpoint = "/api/username/stream" if stream else "/api/username"
    response = client.post(endpoint, json={"username": "octocat", "deep": True, "scope": "standard"})
    assert response.status_code == 200
    wire = response.get_data(as_text=True)
    if stream:
        received = [json.loads(line) for line in wire.splitlines()]
        shown = received[-1]["data"]
        if not cached:
            assert len([e for e in received if e["type"] == "found"]) == 2
            assert [e["count"] for e in received if e["type"] == "found_locked"] == [1, 2]
    else:
        shown = response.get_json()
    assert shown["guest_preview"] == {"visible_cards": 2, "hidden_cards": 2, "requires_sign_in": True}
    assert shown["results"]["profiles"] == cards[:2]
    assert shown["summary"]["total"] == 4
    assert "HiddenThird" not in wire and "hiddenthird.example" not in wire
    assert "HiddenFourth" not in wire and "hiddenfourth.example" not in wire
    assert full == original and app_module._cache.get(key) == original
    signed = client.post(endpoint, json={"username": "octocat", "deep": True, "scope": "standard"},
                         headers={"Authorization": f"Bearer {_token()}"})
    signed_wire = signed.get_data(as_text=True)
    assert "HiddenThird" in signed_wire and "HiddenFourth" in signed_wire
    assert "guest_preview" not in signed_wire

def test_guest_gets_five_quick_scans_a_day(client):
    codes = [_scan(client).status_code for _ in range(plans.GUEST_SCANS_PER_DAY + 1)]
    assert codes[:-1] == [200] * plans.GUEST_SCANS_PER_DAY
    assert codes[-1] == 429
    assert _scan(client).get_json()["code"] == "guest_limit"

@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("cached", [False, True])
def test_guest_standard_requires_signin_before_scan_or_cache(client, monkeypatch, stream, cached):
    import services.search as search
    calls = []
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    if cached:
        app_module._cache.set(app_module._cache_key("username_full", "octocat"), _full_result())

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("A guest must never start a Standard scan")

    monkeypatch.setattr(search, "_run_full", forbidden)
    monkeypatch.setattr(search, "stream_username", forbidden)
    endpoint = "/api/username/stream" if stream else "/api/username"
    for _ in range(plans.GUEST_SCANS_PER_DAY + 1):
        r = client.post(endpoint, json={"username": "octocat", "scope": "full"},
                        headers={"X-Forwarded-For": "8.8.8.8"})
        assert r.status_code == 401 and r.get_json()["code"] == "sign_in_required"
        assert "hidden.example" not in r.get_data(as_text=True)
    assert calls == []
    # Refused Standard requests must leave the guest's Quick allowance intact.
    for _ in range(plans.GUEST_SCANS_PER_DAY):
        assert _scan(client).status_code == 200
    assert _scan(client).get_json()["code"] == "guest_limit"

@pytest.mark.parametrize("cached", [False, True])
def test_guest_quick_stream_still_works(client, monkeypatch, cached):
    import services.search as search
    quick = {"status": "ok", "query": {"scope": "standard"}, "summary": {}, "results": {}}
    calls = []
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    if cached:
        app_module._cache.set(app_module._cache_key("username", "octocat", False), quick)

    def events(username, deep, scope):
        calls.append((username, deep, scope))
        yield {"type": "complete", "data": quick}

    monkeypatch.setattr(search, "stream_username", events)
    r = client.post("/api/username/stream", json={"username": "octocat"})
    assert r.status_code == 200
    shown = json.loads(r.get_data(as_text=True))["data"]
    assert shown["query"] == quick["query"]
    assert shown["guest_preview"] == {"visible_cards": 0, "hidden_cards": 0, "requires_sign_in": True}
    assert calls == ([] if cached else [("octocat", False, "standard")])
