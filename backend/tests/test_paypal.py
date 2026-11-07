"""PayPal grants require account ownership and provider-confirmed exact payment."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

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


def test_currency_quote_and_capture_are_server_owned(monkeypatch):
    monkeypatch.setattr(paypal, "_rates", lambda: {"EUR": Decimal("0.9"), "JPY": Decimal("150")})
    client = app_module.app.test_client()
    response = client.get("/api/billing/paypal/quotes")
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    choices = {choice["code"]: choice for choice in response.get_json()["currencies"]}
    assert choices["EUR"]["amount"] == "3.59"
    assert choices["JPY"]["amount"] == "599"
    captured = {}
    def call(method, path, **kwargs):
        captured.update(kwargs["json"])
        return {"id": ORDER, "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=" + ORDER}]}
    monkeypatch.setattr(paypal, "_call", call)
    response = client.post("/api/billing/paypal/order", json={"plan": "extended", "currency": "EUR",
                           "quote": choices["EUR"]["quote"], "amount": "0.01"})
    assert response.status_code == 200
    assert captured["purchase_units"][0]["amount"] == {"currency_code": "EUR", "value": "3.59"}
    intent = store.store.get(paypal._path(ORDER))
    assert intent["amount"] == "3.59" and intent["currency"] == "EUR"
    result = paid()
    unit = result["purchase_units"][0]
    unit["custom_id"] = intent["binding"]
    unit["amount"] = {"currency_code": "EUR", "value": "3.59"}
    unit["payments"]["captures"][0]["amount"] = {"currency_code": "EUR", "value": "3.59"}
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: result)
    assert paypal.settle(ORDER, uid="dev-test-user")["applied"]
    assert plans.get_account("dev-test-user")["extended_pack_scans_left"] == 10


@pytest.mark.parametrize("bad", ["different_user", "currency", "tamper", "expired", "unsupported"])
def test_invalid_quote_never_creates_order(monkeypatch, bad):
    monkeypatch.setattr(paypal.time, "time", lambda: 100000)
    token = paypal._sign_quote("dev-test-user", "EUR", "3.59")
    uid, currency = "dev-test-user", "EUR"
    if bad == "different_user": uid = "other-user"
    if bad == "currency": currency = "GBP"
    if bad == "tamper": token += "x"
    if bad == "unsupported": currency = "CNY"
    if bad == "expired": monkeypatch.setattr(paypal.time, "time", lambda: 100000 + paypal.QUOTE_TTL_SECONDS)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: pytest.fail("Invalid quote must not create an order"))
    with pytest.raises(ValueError):
        paypal.checkout(uid, currency, token)


def test_quote_endpoint_requires_login(monkeypatch):
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    assert app_module.app.test_client().get("/api/billing/paypal/quotes").status_code == 401


@pytest.mark.parametrize("bad_field", ["currency", "amount"])
def test_partial_stored_quote_never_grants(monkeypatch, bad_field):
    intent = {"uid": "dev-test-user", "binding": "binding", "applied": False,
              "currency": "EUR", "amount": "3.59"}
    del intent[bad_field]
    store.store.set(paypal._path(ORDER), intent)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: paid())
    assert not paypal.settle(ORDER, uid="dev-test-user")["applied"]


def test_reference_rate_outage_preserves_usd(monkeypatch):
    def unavailable(*args, **kwargs):
        raise paypal.requests.Timeout()
    monkeypatch.setattr(paypal.requests, "get", unavailable)
    monkeypatch.setattr(paypal, "_fx_cache", {"until": 0, "rates": {}})
    assert [item["code"] for item in paypal.quotes("dev-test-user")["currencies"]] == ["USD"]


def test_reference_rates_filter_stale_invalid_and_restricted_currencies(monkeypatch):
    import json
    today = date.today()
    rows = [
        {"base": "USD", "quote": "EUR", "date": str(today), "rate": 0.9},
        {"base": "USD", "quote": "GBP", "date": str(today - timedelta(days=8)), "rate": 0.8},
        {"base": "USD", "quote": "AUD", "date": str(today), "rate": -1},
        {"base": "USD", "quote": "CNY", "date": str(today), "rate": 7},
    ]
    class Response:
        def raise_for_status(self): pass
        def iter_content(self, _): yield json.dumps(rows).encode()
        def close(self): pass
    monkeypatch.setattr(paypal.requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(paypal, "_fx_cache", {"until": 0, "rates": {}})
    assert paypal._rates() == {"EUR": Decimal("0.9")}
