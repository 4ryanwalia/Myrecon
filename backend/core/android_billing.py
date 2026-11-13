"""Minimal Firebase RTDB telemetry for Android paid users and amounts."""
import re
import time

import requests

from core import store as storage

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_ALLOWED_PRODUCTS = frozenset({
    "myrecon_scan_pack_5",
    "myrecon_pro_monthly",
    "myrecon_pro_yearly",
})
_MAX_MICROS = 100_000_000_000_000  # 100M currency units safety bound


class Unavailable(Exception):
    pass


class Rejected(Exception):
    pass


def configured():
    return storage.store.backend == "rtdb"


def record_purchase(body):
    """Record anonymized Android purchase metrics without storing any scan data."""
    if not configured():
        raise Unavailable()
    if not isinstance(body, dict):
        raise Rejected()

    install_id = body.get("install_id")
    product_id = body.get("product_id")
    purchase_key = body.get("purchase_key")
    currency = body.get("price_currency_code")
    formatted = body.get("formatted_price")
    micros = body.get("price_amount_micros")

    if (
        not isinstance(install_id, str)
        or not _UUID.fullmatch(install_id)
        or not isinstance(product_id, str)
        or product_id not in _ALLOWED_PRODUCTS
        or not isinstance(purchase_key, str)
        or not _HASH.fullmatch(purchase_key)
        or not isinstance(currency, str)
        or not _CURRENCY.fullmatch(currency)
        or not isinstance(formatted, str)
        or not 1 <= len(formatted.strip()) <= 32
        or isinstance(micros, bool)
        or not isinstance(micros, int)
        or not 0 <= micros <= _MAX_MICROS
    ):
        raise Rejected()

    clean_formatted = formatted.strip()
    now_ms = int(time.time() * 1000)

    # Fast idempotency check before transaction.
    try:
        if storage.store.get(f"android_billing/purchases/{purchase_key}"):
            return {"recorded": "already_recorded"}
    except (requests.RequestException, RuntimeError) as exc:
        raise Unavailable() from exc

    outcome = {"recorded": "recorded"}

    def apply(current):
        current = current or {}
        purchases = current.setdefault("purchases", {})
        if purchase_key in purchases:
            outcome["recorded"] = "already_recorded"
            return current

        purchases[purchase_key] = {
            "install_id": install_id,
            "product_id": product_id,
            "price_amount_micros": micros,
            "price_currency_code": currency,
            "formatted_price": clean_formatted,
            "at": now_ms,
        }

        paid_users = current.setdefault("paid_users", {})
        user = paid_users.get(install_id) or {
            "install_id": install_id,
            "first_paid_at": now_ms,
            "purchase_count": 0,
            "total_micros_by_currency": {},
        }
        user["last_paid_at"] = now_ms
        user["latest_product_id"] = product_id
        user["latest_formatted_price"] = clean_formatted
        user["latest_currency"] = currency
        user["latest_amount_micros"] = micros
        user["purchase_count"] = int(user.get("purchase_count", 0) or 0) + 1
        user_totals = user.setdefault("total_micros_by_currency", {})
        user_totals[currency] = int(user_totals.get(currency, 0) or 0) + micros
        paid_users[install_id] = user

        summary = current.setdefault("summary", {})
        summary["paid_users_count"] = len(paid_users)
        summary["total_purchases"] = int(summary.get("total_purchases", 0) or 0) + 1
        totals = summary.setdefault("totals_by_currency_micros", {})
        totals[currency] = int(totals.get(currency, 0) or 0) + micros
        summary["updated_at"] = now_ms
        outcome["recorded"] = "recorded"
        outcome["paid_users_count"] = summary["paid_users_count"]
        return current

    try:
        storage.store.transaction("android_billing", apply)
    except (requests.RequestException, RuntimeError) as exc:
        raise Unavailable() from exc
    return outcome


def register_routes(app, json_body, responses):
    from flask import request

    @app.route("/api/android/billing/record", methods=["POST", "OPTIONS"])
    def android_billing_record():
        if request.method == "OPTIONS":
            return ("", 204)
        try:
            return responses.ok(record_purchase(json_body()))
        except Rejected:
            return responses.error(
                "Invalid purchase telemetry payload.",
                status=400,
                code="invalid_billing_telemetry",
            )
        except Unavailable:
            return responses.error(
                "Billing telemetry storage is temporarily unavailable.",
                status=503,
                code="billing_unavailable",
            )
