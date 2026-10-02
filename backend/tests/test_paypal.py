"""PayPal grants require account ownership and provider-confirmed exact payment."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
import app as app_module
import config
from core import paypal, plans, store

ORDER = "TESTORDER123456789"


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    mem = store._MemoryStore()
    monkeypatch.setattr(store, "store", mem)
    monkeypatch.setattr(plans, "store", mem)
    monkeypatch.setattr(store, "persistent", lambda: True)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "PAYPAL_CLIENT_ID", "test-client")
    monkeypatch.setattr(config, "PAYPAL_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(config, "PAYPAL_WEBHOOK_ID", "test-webhook")
    monkeypatch.setattr(config, "PAYPAL_ENV", "sandbox")
    store.store.set(paypal._path(ORDER), {"uid": "dev-test-user", "binding": "binding", "applied": False})


def paid():
    return {"id": ORDER, "intent": "CAPTURE", "status": "COMPLETED", "purchase_units": [{
        "reference_id": "extended", "custom_id": "binding", "amount": {"currency_code": "USD", "value": "3.99"},
        "payments": {"captures": [{"id": "CAPTURE123", "status": "COMPLETED", "final_capture": True,
                                  "amount": {"currency_code": "USD", "value": "3.99"}}]}}]}


def test_checkout_server_owns_price_and_binding(monkeypatch):
    captured = {}
    def call(method, path, **kwargs):
        captured.update(kwargs["json"])
        return {"id": ORDER, "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=" + ORDER}]}
    monkeypatch.setattr(paypal, "_call", call)
    response = app_module.app.test_client().post("/api/billing/paypal/order", json={"plan": "extended", "uid": "attacker", "amount": 1})
    assert response.status_code == 200
    assert captured["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "3.99"}
    assert store.store.get(paypal._path(ORDER))["uid"] == "dev-test-user"
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 0


def test_auth_required(monkeypatch):
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    for endpoint in ("order", "capture"):
        assert app_module.app.test_client().post("/api/billing/paypal/" + endpoint, json={}).status_code == 401


def test_sandbox_disabled_in_production(monkeypatch):
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    assert paypal.enabled() is False
    monkeypatch.setattr(config, "PAYPAL_ENV", "live")
    assert paypal.enabled() is True
    monkeypatch.setattr(store, "persistent", lambda: False)
    assert paypal.enabled() is False


def test_missing_webhook_disables_sales(monkeypatch):
    monkeypatch.setattr(config, "PAYPAL_WEBHOOK_ID", "")
    assert not paypal.enabled()


def test_wrong_owner_never_calls_paypal(monkeypatch):
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: pytest.fail("Must check ownership first"))
    with pytest.raises(ValueError):
        paypal.settle(ORDER, uid="attacker", capture=True)


@pytest.mark.parametrize("change", ["price", "currency", "binding", "status", "capture_status", "capture_price", "capture_currency", "extra_capture", "extra_unit", "order_id", "final_capture", "no_capture"])
def test_invalid_confirmation_never_grants(monkeypatch, change):
    order = paid()
    unit = order["purchase_units"][0]
    capture = unit["payments"]["captures"][0]
    if change == "price": unit["amount"]["value"] = "0.01"
    elif change == "currency": unit["amount"]["currency_code"] = "INR"
    elif change == "binding": unit["custom_id"] = "attacker"
    elif change == "status": order["status"] = "APPROVED"
    elif change == "capture_status": capture["status"] = "PENDING"
    elif change == "capture_price": capture["amount"]["value"] = "0.01"
    elif change == "capture_currency": capture["amount"]["currency_code"] = "EUR"
    elif change == "extra_capture": unit["payments"]["captures"].append(deepcopy(capture))
    elif change == "extra_unit": order["purchase_units"].append(deepcopy(unit))
    elif change == "order_id": order["id"] = "OTHERORDER123"
    elif change == "final_capture": capture["final_capture"] = False
    elif change == "no_capture": unit.pop("payments")
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: order)
    assert not paypal.settle(ORDER, uid="dev-test-user")["applied"]
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 0


def test_concurrent_and_repeat_confirmation_grants_once(monkeypatch):
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: paid())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: paypal.settle(ORDER, uid="dev-test-user"), range(20)))
    assert all(result["applied"] for result in results)
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10


def test_capture_timeout_recovers_completed_order(monkeypatch):
    calls = []
    def call(method, path, **kwargs):
        calls.append(method)
        if method == "POST": raise paypal.PayPalError("timeout")
        order = paid()
        if len(calls) == 1: order["status"] = "APPROVED"
        return order
    monkeypatch.setattr(paypal, "_call", call)
    assert paypal.settle(ORDER, uid="dev-test-user", capture=True)["applied"]
    assert calls == ["GET", "POST", "GET"]


def test_changed_approved_amount_is_not_captured(monkeypatch):
    order = paid()
    order["status"] = "APPROVED"
    order["purchase_units"][0]["amount"]["value"] = "99.99"
    def call(method, path, **kwargs):
        assert method == "GET"
        return order
    monkeypatch.setattr(paypal, "_call", call)
    assert not paypal.settle(ORDER, uid="dev-test-user", capture=True)["applied"]


def test_database_failure_retry_does_not_double_grant(monkeypatch):
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: paid())
    original = store.store.transaction
    def fail(path, fn):
        if path == paypal._path(ORDER): raise RuntimeError("temporary store failure")
        return original(path, fn)
    monkeypatch.setattr(store.store, "transaction", fail)
    with pytest.raises(RuntimeError): paypal.settle(ORDER, uid="dev-test-user")
    monkeypatch.setattr(store.store, "transaction", original)
    assert paypal.settle(ORDER, uid="dev-test-user")["applied"]
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10


def test_webhook_verifies_before_granting(monkeypatch):
    headers = {name: "test" for name in ("Paypal-Auth-Algo", "Paypal-Cert-Url", "Paypal-Transmission-Id", "Paypal-Transmission-Sig", "Paypal-Transmission-Time")}
    event = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"supplementary_data": {"related_ids": {"order_id": ORDER}}}}
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: {"verification_status": "FAILURE"})
    with pytest.raises(ValueError): paypal.webhook(event, headers)
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 0
    monkeypatch.setattr(paypal, "_call", lambda method, path, **k: {"verification_status": "SUCCESS"} if "verify-webhook" in path else paid())
    assert paypal.webhook(event, headers)["applied"]


@pytest.mark.parametrize("value", [None, "../foo", "lowercase", {}, "ABC/DEFGHIJK"])
def test_invalid_order_ids(value):
    with pytest.raises(ValueError): paypal.settle(value)


def test_secrets_not_in_plans():
    info = app_module.app.test_client().get("/api/plans").get_json()
    assert info["paypal_payments"]["enabled"]
    assert "test-secret" not in str(info)
    assert "test-client" not in str(info)
