"""Minimal Firebase RTDB telemetry tests for Android paid users and amounts."""
import copy
import pytest
import requests

from core import android_billing as b

INSTALL_A = "11111111-1111-1111-1111-111111111111"
INSTALL_B = "22222222-2222-2222-2222-222222222222"
KEY_1 = "a" * 64
KEY_2 = "b" * 64
KEY_3 = "c" * 64


class Store:
    backend = "rtdb"

    def __init__(self):
        self.data = {}

    def get(self, path):
        node = self.data
        for key in path.split("/"):
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return copy.deepcopy(node)

    def transaction(self, path, callback):
        self.data[path] = callback(copy.deepcopy(self.data.get(path)))


@pytest.fixture
def rtdb(monkeypatch):
    store = Store()
    monkeypatch.setattr(b.storage, "store", store)
    return store


def test_records_paid_user_count_and_amounts_idempotently(rtdb):
    first = {
        "install_id": INSTALL_A,
        "product_id": "myrecon_scan_pack_5",
        "purchase_key": KEY_1,
        "price_amount_micros": 99_000_000,
        "price_currency_code": "INR",
        "formatted_price": "₹99.00",
        # Even if a client tries sending extra fields, scans must never be stored.
        "username": "should_not_persist",
        "scans": ["secret"],
    }
    res1 = b.record_purchase(first)
    assert res1 == {"recorded": "recorded", "paid_users_count": 1}
    # Duplicate submission with same purchase_key does not double-count.
    assert b.record_purchase(first) == {"recorded": "already_recorded"}

    # Second purchase by same user increments purchase count but keeps paid_users_count == 1.
    second = {
        "install_id": INSTALL_A,
        "product_id": "myrecon_scan_pack_5",
        "purchase_key": KEY_2,
        "price_amount_micros": 99_000_000,
        "price_currency_code": "INR",
        "formatted_price": "₹99.00",
    }
    res2 = b.record_purchase(second)
    assert res2 == {"recorded": "recorded", "paid_users_count": 1}

    # Different user in USD increments paid_users_count to 2.
    third = {
        "install_id": INSTALL_B,
        "product_id": "myrecon_pro_monthly",
        "purchase_key": KEY_3,
        "price_amount_micros": 1_990_000,
        "price_currency_code": "USD",
        "formatted_price": "$1.99",
    }
    res3 = b.record_purchase(third)
    assert res3 == {"recorded": "recorded", "paid_users_count": 2}

    billing = rtdb.data["android_billing"]
    assert billing["summary"]["paid_users_count"] == 2
    assert billing["summary"]["total_purchases"] == 3
    assert billing["summary"]["totals_by_currency_micros"] == {
        "INR": 198_000_000,
        "USD": 1_990_000,
    }
    user_a = billing["paid_users"][INSTALL_A]
    assert user_a["purchase_count"] == 2
    assert user_a["total_micros_by_currency"] == {"INR": 198_000_000}
    assert "username" not in str(billing)
    assert "should_not_persist" not in str(billing)


@pytest.mark.parametrize(
    "bad",
    [
        {"install_id": "not-a-uuid"},
        {"product_id": "unknown_sku"},
        {"purchase_key": "short"},
        {"price_currency_code": "usd"},
        {"price_amount_micros": -1},
        {"price_amount_micros": True},
        {"formatted_price": ""},
    ],
)
def test_rejects_invalid_payloads_without_writing(rtdb, bad):
    payload = {
        "install_id": INSTALL_A,
        "product_id": "myrecon_scan_pack_5",
        "purchase_key": KEY_1,
        "price_amount_micros": 99_000_000,
        "price_currency_code": "INR",
        "formatted_price": "₹99.00",
    }
    payload.update(bad)
    with pytest.raises(b.Rejected):
        b.record_purchase(payload)
    assert rtdb.data == {}


def test_memory_backend_fails_closed(monkeypatch):
    store = Store()
    store.backend = "memory"
    monkeypatch.setattr(b.storage, "store", store)
    with pytest.raises(b.Unavailable):
        b.record_purchase({
            "install_id": INSTALL_A,
            "product_id": "myrecon_scan_pack_5",
            "purchase_key": KEY_1,
            "price_amount_micros": 99_000_000,
            "price_currency_code": "INR",
            "formatted_price": "₹99.00",
        })


def test_http_endpoint_record_and_validation(rtdb, monkeypatch):
    from flask import Flask
    from core import responses

    app = Flask(__name__)

    def json_body():
        from flask import request
        return request.get_json(silent=True) or {}

    b.register_routes(app, json_body, responses)
    client = app.test_client()

    ok_resp = client.post(
        "/api/android/billing/record",
        json={
            "install_id": INSTALL_A,
            "product_id": "myrecon_scan_pack_5",
            "purchase_key": KEY_1,
            "price_amount_micros": 99_000_000,
            "price_currency_code": "INR",
            "formatted_price": "₹99",
        },
    )
    assert ok_resp.status_code == 200
    assert ok_resp.get_json()["recorded"] == "recorded"

    bad_resp = client.post(
        "/api/android/billing/record",
        json={"install_id": "bad"},
    )
    assert bad_resp.status_code == 400
    assert bad_resp.get_json()["code"] == "invalid_billing_telemetry"

    rtdb.backend = "memory"
    unavail_resp = client.post(
        "/api/android/billing/record",
        json={
            "install_id": INSTALL_A,
            "product_id": "myrecon_scan_pack_5",
            "purchase_key": KEY_2,
            "price_amount_micros": 1_990_000,
            "price_currency_code": "USD",
            "formatted_price": "$1.99",
        },
    )
    assert unavail_resp.status_code == 503
    assert unavail_resp.get_json()["code"] == "billing_unavailable"


@pytest.mark.parametrize(
    "exc",
    [
        requests.RequestException("429 Too Many Requests"),
        RuntimeError("ETag exhaustion"),
    ],
)
def test_rtdb_request_or_runtime_error_returns_503_billing_unavailable(monkeypatch, exc):
    from flask import Flask, request
    from core import responses

    class FailingStore:
        backend = "rtdb"

        def get(self, path):
            raise exc

        def transaction(self, path, callback):
            raise exc

    monkeypatch.setattr(b.storage, "store", FailingStore())
    app = Flask(__name__)
    b.register_routes(app, lambda: request.get_json(silent=True) or {}, responses)
    client = app.test_client()

    resp = client.post(
        "/api/android/billing/record",
        json={
            "install_id": INSTALL_A,
            "product_id": "myrecon_scan_pack_5",
            "purchase_key": KEY_3,
            "price_amount_micros": 99_000_000,
            "price_currency_code": "INR",
            "formatted_price": "₹99",
        },
    )
    assert resp.status_code == 503
    assert resp.get_json()["code"] == "billing_unavailable"
