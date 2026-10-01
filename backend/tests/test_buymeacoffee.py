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
    data = event(bmc.checkout("u")["activation_code"])
    assert send(client, data, sig).status_code == 400
    assert plans.get_account("u")["tier"] == "free"


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
    payload = event(bmc.checkout("u")["activation_code"])
    prefix, _, key = field.partition(".")
    if prefix == "data":
        payload["data"][key] = value
    elif prefix == "item":
        payload["data"]["extras"][0][key] = value
    else:
        payload[field] = value
    assert send(client, payload).get_json()["applied"] is False
    assert plans.get_account("u")["tier"] == "free"


def test_retries_and_updates_add_only_one_pack(client):
    payload = event(bmc.checkout("u")["activation_code"])
    assert send(client, payload).get_json()["applied"] is True
    payload.update(type="extra_purchase.updated", event_id=100, attempt=2)
    assert send(client, payload).get_json()["applied"] is True
    assert plans.get_account("u")["extended_pack_scans_left"] == 10
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
    payload = event(bmc.checkout("u")["activation_code"])
    original = store.store.transaction
    failed = [False]

    def fail_ledger(path, fn, **kw):
        if path.startswith("web/payments/") and not failed[0]:
            failed[0] = True
            raise RuntimeError("temporary storage failure")
        return original(path, fn, **kw)

    monkeypatch.setattr(store.store, "transaction", fail_ledger)
    assert send(client, payload).status_code == 500
    assert send(client, payload).get_json()["applied"] is True
    assert plans.get_account("u")["extended_pack_scans_left"] == 10


def test_expired_code_rejects_new_purchase_but_accepts_delayed_delivery(client, monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(bmc.time, "time", lambda: now)
    code = bmc.checkout("u")["activation_code"]
    payload = event(code)
    monkeypatch.setattr(bmc.time, "time", lambda: now + 8 * 86400)
    assert send(client, payload).get_json()["applied"] is True
    payload["data"].update(id=124, created_at=now + 8 * 86400)
    assert send(client, payload).get_json()["applied"] is False


@pytest.mark.parametrize("payload", [[], None, {"live_mode": True, "data": []}])
def test_signed_malformed_shapes_do_not_crash(client, payload):
    assert send(client, payload).status_code == 200
