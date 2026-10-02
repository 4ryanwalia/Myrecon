"""International payments: authenticated checkout and signed, retry-safe grants."""
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import app as app_module
import config
from core import buymeacoffee as bmc, plans, store


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    mem = store._MemoryStore()
    monkeypatch.setattr(store, "store", mem)
    monkeypatch.setattr(plans, "store", mem)
    monkeypatch.setattr(store, "persistent", lambda: True)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "BUYMEACOFFEE_SHOP_URL", "https://buymeacoffee.com/myrecon/e/12345")
    monkeypatch.setattr(config, "BUYMEACOFFEE_ITEM_ID", "12345")
    monkeypatch.setattr(config, "BUYMEACOFFEE_WEBHOOK_SECRET", "test-signing-secret")


@pytest.fixture
def client():
    return app_module.app.test_client()


def event(code, purchase=123):
    return {"type": "extra_purchase.created", "live_mode": True, "event_id": 99,
            "data": {"id": purchase, "status": "succeeded", "refunded": "false",
                     "amount": 3.99, "currency": "USD", "created_at": int(time.time()),
                     "extras": [{"id": 12345, "quantity": 1, "amount": 3.99,
                                 "currency": "USD", "question_answers": [code]}]}}


def send(client, payload, signature=None):
    raw = json.dumps(payload).encode()
    sig = hmac.new(config.BUYMEACOFFEE_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/billing/buymeacoffee/webhook", data=raw,
                       headers={"x-signature-sha256": sig if signature is None else signature,
                                "Content-Type": "application/json"})


def status(client, code):
    return client.post("/api/billing/buymeacoffee/status", json={"activation_code": code})


def test_checkout_requires_signin(client, monkeypatch):
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    assert client.post("/api/billing/buymeacoffee/checkout", json={"plan": "extended"}).status_code == 401


def test_checkout_price_and_code_are_server_owned(client):
    result = client.post("/api/billing/buymeacoffee/checkout",
                         json={"plan": "extended", "amount": 1, "uid": "attacker"})
    assert result.status_code == 200
    data = result.get_json()
    assert data["amount"] == 399 and data["currency"] == "USD"
    assert plans.get_account("dev-test-user")["tier"] == "free"
    assert send(client, event(data["activation_code"])).get_json()["applied"] is True
    acct = plans.get_account("dev-test-user")
    assert acct["extended_pack_scans_left"] == 10
    assert acct["deep_search_enabled"] and acct["standard_scans_unlimited"]
    assert plans.get_account("attacker")["tier"] == "free"
    assert status(client, data["activation_code"]).get_json() == {
        "status": "ok", "payment_status": "applied", "expires_at": data["expires_at"]}


def test_status_requires_signin(client, monkeypatch):
    code = bmc.checkout("dev-test-user")["activation_code"]
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    assert status(client, code).status_code == 401


def test_status_is_pending_for_owner_and_does_not_expose_identity(client):
    checkout = bmc.checkout("dev-test-user")
    response = status(client, "  " + checkout["activation_code"] + "  ")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "payment_status": "pending",
                                  "expires_at": checkout["expires_at"]}


@pytest.mark.parametrize("code", [None, "", "bad", "MR-" + "a" * 31,
                                 "MR-" + "A" * 32, 123, [], {}])
def test_status_rejects_malformed_codes(client, code):
    assert status(client, code).status_code == 422


def test_status_rejects_non_object_body(client):
    assert client.post("/api/billing/buymeacoffee/status", json=["invalid"]).status_code == 422


def test_status_hides_other_users_and_unknown_codes(client):
    other_code = bmc.checkout("other")["activation_code"]
    other = status(client, other_code)
    unknown = status(client, "MR-" + "0" * 32)
    assert other.status_code == unknown.status_code == 404
    assert other.get_json() == unknown.get_json()
    spoofed = client.post("/api/billing/buymeacoffee/status",
                          json={"activation_code": other_code, "uid": "other"})
    assert spoofed.status_code == 404


def test_status_reads_existing_checkout_when_sales_are_disabled(client, monkeypatch):
    code = bmc.checkout("dev-test-user")["activation_code"]
    monkeypatch.setattr(config, "BUYMEACOFFEE_WEBHOOK_SECRET", "")
    assert status(client, code).get_json()["payment_status"] == "pending"


def test_status_expires_without_granting_a_pack(client, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(bmc.time, "time", lambda: now)
    checkout = bmc.checkout("dev-test-user")
    monkeypatch.setattr(bmc.time, "time", lambda: checkout["expires_at"] + 1)
    assert status(client, checkout["activation_code"]).get_json() == {
        "status": "ok", "payment_status": "expired", "expires_at": checkout["expires_at"]}
    assert plans.get_account("dev-test-user")["tier"] == "free"


def test_test_webhook_cannot_confirm_checkout(client):
    code = bmc.checkout("dev-test-user")["activation_code"]
    payload = event(code)
    payload["live_mode"] = False
    assert send(client, payload).get_json()["applied"] is False
    assert status(client, code).get_json()["payment_status"] == "pending"
    assert plans.get_account("dev-test-user")["tier"] == "free"


def test_paid_account_and_modified_retry_do_not_confirm_new_checkout(client, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(bmc.time, "time", lambda: now)
    first = bmc.checkout("dev-test-user")["activation_code"]
    payload = event(first)
    assert send(client, payload).get_json()["applied"] is True
    second = bmc.checkout("dev-test-user")["activation_code"]
    assert status(client, second).get_json()["payment_status"] == "pending"
    payload["data"]["extras"][0]["question_answers"] = [second]
    assert send(client, payload).get_json()["applied"] is False
    assert status(client, second).get_json()["payment_status"] == "pending"
    assert status(client, first).get_json()["payment_status"] == "applied"
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10


def test_other_plans_not_sold(client):
    assert client.post("/api/billing/buymeacoffee/checkout", json={"plan": "monthly"}).status_code == 422


@pytest.mark.parametrize("setting,value", [
    ("BUYMEACOFFEE_WEBHOOK_SECRET", ""), ("BUYMEACOFFEE_ITEM_ID", ""),
    ("BUYMEACOFFEE_SHOP_URL", "https://evil.example/myrecon/e/12345"),
    ("BUYMEACOFFEE_SHOP_URL", "https://buymeacoffee.com/myrecon/e/999"),
    ("BUYMEACOFFEE_SHOP_URL", "http://buymeacoffee.com/myrecon/e/12345"),
    ("BUYMEACOFFEE_SHOP_URL", "https://user:pass@buymeacoffee.com/myrecon/e/12345"),
])
def test_missing_or_invalid_config_disables_checkout(client, monkeypatch, setting, value):
    monkeypatch.setattr(config, setting, value)
    assert bmc.enabled() is False
    assert client.get("/api/plans").get_json()["international_payments"]["enabled"] is False
    assert client.post("/api/billing/buymeacoffee/checkout", json={"plan": "extended"}).status_code == 503


def test_persistent_store_required(client, monkeypatch):
    monkeypatch.setattr(store, "persistent", lambda: False)
    assert bmc.enabled() is False
    assert client.post("/api/billing/buymeacoffee/checkout", json={"plan": "extended"}).status_code == 503


def test_secret_not_public(client):
    assert "test-signing-secret" not in client.get("/api/plans").get_data(as_text=True)


@pytest.mark.parametrize("sig", ["", "bad", "0" * 64])
def test_forged_signatures_do_not_grant(client, sig):
    code = bmc.checkout("u")["activation_code"]
    data = event(code)
    assert send(client, data, sig).status_code == 400
    assert plans.get_account("u")["tier"] == "free"
    assert bmc.payment_status("u", code)["payment_status"] == "pending"


@pytest.mark.parametrize("field,value", [
    ("live_mode", False), ("live_mode", "true"), ("type", "donation.created"),
    ("data.status", "pending"), ("data.refunded", "true"),
    ("data.currency", "INR"), ("data.amount", 3.98), ("data.amount", "NaN"),
    ("data.id", "123"), ("data.extras", []),
    ("item.id", 999), ("item.quantity", 2), ("item.quantity", True),
    ("item.amount", 1), ("item.currency", "INR"),
    ("item.question_answers", ["MR-" + "0" * 32]),
    ("item.question_answers", []), ("item.question_answers", ["u"]),
    ("data.created_at", 0),
])
def test_ineligible_purchase_does_not_grant(client, field, value):
    code = bmc.checkout("u")["activation_code"]
    payload = event(code)
    prefix, _, key = field.partition(".")
    if prefix == "data":
        payload["data"][key] = value
    elif prefix == "item":
        payload["data"]["extras"][0][key] = value
    else:
        payload[field] = value
    assert send(client, payload).get_json()["applied"] is False
    assert plans.get_account("u")["tier"] == "free"
    assert bmc.payment_status("u", code)["payment_status"] == "pending"


def test_retries_and_updates_add_only_one_pack(client):
    code = bmc.checkout("u")["activation_code"]
    payload = event(code)
    assert send(client, payload).get_json()["applied"] is True
    payload.update(type="extra_purchase.updated", event_id=100, attempt=2)
    assert send(client, payload).get_json()["applied"] is True
    assert plans.get_account("u")["extended_pack_scans_left"] == 10
    assert bmc.payment_status("u", code)["payment_status"] == "applied"
    payload["data"]["id"] = 124
    assert send(client, payload).get_json()["applied"] is True
    assert plans.get_account("u")["extended_pack_scans_left"] == 20


def test_concurrent_retries_are_safe():
    payload = event(bmc.checkout("u")["activation_code"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(bmc.settle, [payload] * 16))
    assert plans.get_account("u")["extended_pack_scans_left"] == 10


def test_same_purchase_cannot_move_to_another_account(client):
    first = event(bmc.checkout("u")["activation_code"])
    second = event(bmc.checkout("other")["activation_code"])
    assert send(client, first).get_json()["applied"] is True
    assert send(client, second).get_json()["applied"] is False
    assert plans.get_account("other")["tier"] == "free"


def test_storage_failure_retries_without_lost_or_duplicate_credits(client, monkeypatch):
    code = bmc.checkout("u")["activation_code"]
    payload = event(code)
    original = store.store.transaction
    failed = [False]

    def fail_ledger(path, fn, **kw):
        if path.startswith("web/payments/") and not failed[0]:
            failed[0] = True
            raise RuntimeError("temporary storage failure")
        return original(path, fn, **kw)

    monkeypatch.setattr(store.store, "transaction", fail_ledger)
    assert send(client, payload).status_code == 500
    assert bmc.payment_status("u", code)["payment_status"] == "pending"
    assert send(client, payload).get_json()["applied"] is True
    assert plans.get_account("u")["extended_pack_scans_left"] == 10
    assert bmc.payment_status("u", code)["payment_status"] == "applied"


def test_checkout_marker_failure_recovers_on_retry_and_preserves_record(client, monkeypatch):
    code = bmc.checkout("dev-test-user")["activation_code"]
    path = bmc._path(code)
    record = store.store.get(path)
    record["existing_field"] = "preserve"
    store.store.set(path, record)
    original = store.store.transaction
    failed = [False]

    def fail_marker(update_path, fn, **kw):
        if update_path == path and not failed[0]:
            failed[0] = True
            raise RuntimeError("temporary checkout write failure")
        return original(update_path, fn, **kw)

    monkeypatch.setattr(store.store, "transaction", fail_marker)
    payload = event(code)
    assert send(client, payload).status_code == 500
    assert status(client, code).get_json()["payment_status"] == "pending"
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10
    assert send(client, payload).get_json()["applied"] is True
    assert status(client, code).get_json()["payment_status"] == "applied"
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10
    assert store.store.get(path) == {**record, "applied": True}


def test_failed_grant_does_not_mark_checkout_applied(client, monkeypatch):
    code = bmc.checkout("dev-test-user")["activation_code"]
    monkeypatch.setattr(plans, "grant_pass", lambda *args: False)
    assert send(client, event(code)).get_json()["applied"] is False
    assert status(client, code).get_json()["payment_status"] == "pending"
    assert plans.get_account("dev-test-user")["tier"] == "free"


def test_legacy_purchase_retry_confirms_status_without_duplicate_grant(client):
    code = bmc.checkout("dev-test-user")["activation_code"]
    ref = "buymeacoffee:123"
    assert plans.grant_pass("dev-test-user", "extended", ref) is True
    old_owner = {"uid": "dev-test-user", "ref": ref, "existing_field": "preserve"}
    store.store.set("web/bmc_purchases/123", old_owner)
    assert status(client, code).get_json()["payment_status"] == "pending"
    assert send(client, event(code)).get_json()["applied"] is True
    assert status(client, code).get_json()["payment_status"] == "applied"
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10
    assert store.store.get("web/bmc_purchases/123") == {
        **old_owner, "checkout": bmc._path(code)}


@pytest.mark.parametrize("field,value", [("uid", "other"), ("ref", "buymeacoffee:999"),
                                         ("plan", "weekly")])
def test_retry_requires_exact_successful_grant_ledger(client, monkeypatch, field, value):
    code = bmc.checkout("dev-test-user")["activation_code"]
    ref = "buymeacoffee:123"
    ref_key = hashlib.sha256(ref.encode()).hexdigest()[:40]
    ledger = {"uid": "dev-test-user", "ref": ref, "plan": "extended"}
    ledger[field] = value
    store.store.set("web/payments/" + ref_key, ledger)
    monkeypatch.setattr(plans, "grant_pass", lambda *args: False)
    assert send(client, event(code)).get_json()["applied"] is False
    assert status(client, code).get_json()["payment_status"] == "pending"


def test_expired_code_rejects_new_purchase_but_accepts_delayed_delivery(client, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(bmc.time, "time", lambda: now)
    code = bmc.checkout("u")["activation_code"]
    payload = event(code)
    monkeypatch.setattr(bmc.time, "time", lambda: now + 8 * 86400)
    assert bmc.payment_status("u", code)["payment_status"] == "expired"
    assert send(client, payload).get_json()["applied"] is True
    assert bmc.payment_status("u", code)["payment_status"] == "applied"
    payload["data"].update(id=124, created_at=now + 8 * 86400)
    assert send(client, payload).get_json()["applied"] is False


@pytest.mark.parametrize("payload", [[], None, {"live_mode": True, "data": []}])
def test_signed_malformed_shapes_do_not_crash(client, payload):
    assert send(client, payload).status_code == 200
