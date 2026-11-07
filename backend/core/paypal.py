"""Server-owned checkout. Only verified completed captures grant credits."""
import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit

import requests
import config
from core import plans, store

PRICE = "3.99"
SUPPORTED_CURRENCIES = ("USD", "AUD", "CAD", "CHF", "CZK", "DKK", "EUR", "GBP",
                        "HKD", "HUF", "ILS", "JPY", "MXN", "NOK", "NZD", "PHP",
                        "PLN", "SEK", "SGD", "THB", "TWD")
ZERO_DECIMAL = frozenset(("HUF", "JPY", "TWD"))
QUOTE_TTL_SECONDS = 900
_FX_URL = "https://api.frankfurter.dev/v2/rates"
_fx_cache = {"until": 0, "rates": {}}
RETURN_URL = "https://www.myrecon.xyz/pricing.html?paypal=return"
CANCEL_URL = "https://www.myrecon.xyz/pricing.html?paypal=cancel"


class PayPalError(Exception):
    pass


def configured():
    return bool(config.PAYPAL_CLIENT_ID and config.PAYPAL_CLIENT_SECRET
                and config.PAYPAL_WEBHOOK_ID and config.PAYPAL_ENV in ("sandbox", "live")
                and store.persistent())


def enabled():
    # Sandbox credentials must never open sales on the public website.
    return configured() and (config.PAYPAL_ENV == "live" or config.DEV_TEST_ACCOUNT)


def _base():
    return "https://api-m.paypal.com" if config.PAYPAL_ENV == "live" else "https://api-m.sandbox.paypal.com"


def _request(method, path, **kwargs):
    try:
        response = requests.request(method, _base() + path, timeout=15, **kwargs)
        if response.status_code >= 400:
            raise PayPalError("PayPal request failed. Please try again.")
        result = response.json()
        if not isinstance(result, dict):
            raise PayPalError("Invalid PayPal response.")
        return result
    except (requests.RequestException, ValueError):
        raise PayPalError("PayPal is unavailable. Please try again.") from None


def _call(method, path, request_id=None, **kwargs):
    token = _request("POST", "/v1/oauth2/token",
                     auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_CLIENT_SECRET),
                     data={"grant_type": "client_credentials"}).get("access_token")
    if not token:
        raise PayPalError("PayPal authentication failed.")
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
               "Prefer": "return=representation"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    return _request(method, path, headers=headers, **kwargs)


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9]{10,32}", value):
        raise ValueError("Invalid PayPal order.")
    return value


def _path(order_id):
    return "web/paypal_orders/" + config.PAYPAL_ENV + "/" + _id(order_id)


def _rates():
    """Get recent, bounded public reference rates; a failed fetch offers USD only."""
    now = time.time()
    if now < _fx_cache["until"]:
        return _fx_cache["rates"]
    rates = {}
    try:
        response = requests.get(_FX_URL, params={"base": "USD", "quotes": ",".join(SUPPORTED_CURRENCIES[1:])},
                                timeout=4, allow_redirects=False, stream=True)
        try:
            response.raise_for_status()
            data = bytearray()
            for part in response.iter_content(8192):
                data.extend(part)
                if len(data) > 65536:
                    raise ValueError("Invalid exchange-rate response")
            entries = json.loads(data)
        finally:
            response.close()
        if not isinstance(entries, list) or len(entries) > 100:
            raise ValueError("Invalid exchange-rate response")
        today = date.today()
        for item in entries:
            if not isinstance(item, dict) or item.get("base") != "USD":
                continue
            code = item.get("quote")
            if code not in SUPPORTED_CURRENCIES[1:]:
                continue
            day = date.fromisoformat(item["date"])
            rate = Decimal(str(item["rate"]))
            if today - timedelta(days=7) <= day <= today + timedelta(days=1) and rate.is_finite() and Decimal("0.0001") <= rate <= Decimal("100000"):
                rates[code] = rate
    except (requests.RequestException, ValueError, KeyError, TypeError, InvalidOperation, OverflowError):
        rates = {}
    _fx_cache.update(until=now + (3600 if rates else 60), rates=rates)
    return rates


def _sign_quote(uid, currency, amount):
    payload = {"uid": uid, "plan": "extended", "currency": currency, "amount": amount,
               "exp": int(time.time()) + QUOTE_TTL_SECONDS}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    signature = hmac.new(config.PAYPAL_CLIENT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def quotes(uid):
    items = [{"code": "USD", "amount": PRICE, "quote": _sign_quote(uid, "USD", PRICE)}]
    for code, rate in _rates().items():
        unit = Decimal("1") if code in ZERO_DECIMAL else Decimal("0.01")
        amount = (Decimal(PRICE) * rate).quantize(unit, rounding=ROUND_HALF_UP)
        if amount > 0:
            value = format(amount, "f")
            items.append({"code": code, "amount": value, "quote": _sign_quote(uid, code, value)})
    return {"currencies": items, "default_currency": "USD", "expires_in": QUOTE_TTL_SECONDS}


def _quote_amount(uid, currency, token):
    if currency not in SUPPORTED_CURRENCIES or not isinstance(token, str) or len(token) > 2048:
        raise ValueError("Invalid currency or quote. Refresh prices and try again.")
    try:
        encoded, signature = token.split(".")
        expected = hmac.new(config.PAYPAL_CLIENT_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        amount = payload["amount"]
        value = Decimal(amount)
        unit = Decimal("1") if currency in ZERO_DECIMAL else Decimal("0.01")
        if (payload["uid"] != uid or payload["plan"] != "extended" or payload["currency"] != currency
                or type(payload["exp"]) is not int or payload["exp"] <= int(time.time())
                or not isinstance(amount, str) or not value.is_finite() or value <= 0
                or value > Decimal("10000000") or value.quantize(unit) != value):
            raise ValueError
        return amount
    except (ValueError, KeyError, TypeError, InvalidOperation, OverflowError):
        raise ValueError("Price quote expired or invalid. Refresh prices and try again.") from None


def checkout(uid, currency="USD", quote=None):
    # Older clients can continue to create USD orders during a rolling deploy.
    if currency == "USD" and quote is None:
        amount = PRICE
    else:
        amount = _quote_amount(uid, currency, quote)
    binding = uuid.uuid4().hex
    order = _call("POST", "/v2/checkout/orders", request_id=binding, json={
        "intent": "CAPTURE",
        "purchase_units": [{"reference_id": "extended", "custom_id": binding,
                            "description": "MyRecon Extended Scan Pack: 10 Extended credits",
                            "amount": {"currency_code": currency, "value": amount}}],
        "payment_source": {"paypal": {"experience_context": {
            "return_url": RETURN_URL, "cancel_url": CANCEL_URL,
            "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING"}}},
    })
    order_id = _id(order.get("id"))
    url = next((link.get("href") for link in order.get("links", [])
                if link.get("rel") in ("payer-action", "approve")), "")
    parsed = urlsplit(url)
    host = "www.paypal.com" if config.PAYPAL_ENV == "live" else "www.sandbox.paypal.com"
    if (parsed.scheme != "https" or parsed.hostname != host or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise PayPalError("PayPal checkout link is unavailable.")
    # Persist ownership before sending the buyer to PayPal.
    store.store.set(_path(order_id), {"uid": uid, "binding": binding, "applied": False,
                                      "currency": currency, "amount": amount})
    minor_amount = int(Decimal(amount) * (1 if currency in ZERO_DECIMAL else 100))
    return {"order_id": order_id, "url": url, "amount": minor_amount,
            "amount_value": amount, "currency": currency}


def _intent_amount(intent):
    # Orders initiated before multi-currency deployment did not store a price.
    if "currency" not in intent and "amount" not in intent:
        return "USD", Decimal(PRICE)
    currency, amount = intent["currency"], intent["amount"]
    if currency not in SUPPORTED_CURRENCIES or not isinstance(amount, str):
        raise ValueError("Invalid stored payment")
    value = Decimal(amount)
    if not value.is_finite() or value <= 0:
        raise ValueError("Invalid stored payment")
    return currency, value


def _matches_order(order, order_id, intent):
    try:
        currency, amount = _intent_amount(intent)
        units = order["purchase_units"]
        unit = units[0]
        return (order["id"] == order_id and order["intent"] == "CAPTURE" and len(units) == 1
                and unit["reference_id"] == "extended" and unit["custom_id"] == intent["binding"]
                and unit["amount"]["currency_code"] == currency
                and Decimal(unit["amount"]["value"]) == amount)
    except (KeyError, IndexError, TypeError, InvalidOperation, ValueError):
        return False


def _completed(order, order_id, intent):
    try:
        currency, amount = _intent_amount(intent)
        units = order["purchase_units"]
        unit = units[0]
        captures = unit["payments"]["captures"]
        capture = captures[0]
        return (_matches_order(order, order_id, intent) and order["status"] == "COMPLETED"
                and len(captures) == 1 and bool(capture["id"])
                and capture["status"] == "COMPLETED" and capture.get("final_capture") is True
                and capture["amount"]["currency_code"] == currency
                and Decimal(capture["amount"]["value"]) == amount)
    except (KeyError, IndexError, TypeError, InvalidOperation, ValueError):
        return False


def settle(order_id, uid=None, capture=False):
    path = _path(order_id)
    intent = store.store.get(path)
    if not isinstance(intent, dict) or (uid is not None and intent.get("uid") != uid):
        raise ValueError("PayPal checkout not found for this account.")
    if intent.get("applied"):
        return {"applied": True, "pending": False}
    order = _call("GET", "/v2/checkout/orders/" + order_id)
    if capture and order.get("status") == "APPROVED" and _matches_order(order, order_id, intent):
        try:
            _call("POST", "/v2/checkout/orders/" + order_id + "/capture",
                  request_id="capture-" + intent["binding"], json={})
        except PayPalError:
            # A timeout or parallel webhook may have captured it already.
            pass
        order = _call("GET", "/v2/checkout/orders/" + order_id)
    if not _completed(order, order_id, intent):
        return {"applied": False, "pending": True}
    plans.grant_pass(intent["uid"], "extended", "paypal:" + config.PAYPAL_ENV + ":" + order_id)
    store.store.transaction(path, lambda current: {**current, "applied": True})
    return {"applied": True, "pending": False}


def webhook(event, headers):
    fields = {"auth_algo": "Paypal-Auth-Algo", "cert_url": "Paypal-Cert-Url",
              "transmission_id": "Paypal-Transmission-Id",
              "transmission_sig": "Paypal-Transmission-Sig", "transmission_time": "Paypal-Transmission-Time"}
    payload = {key: headers.get(header, "") for key, header in fields.items()}
    if not all(payload.values()):
        raise ValueError("Invalid PayPal webhook signature.")
    payload.update(webhook_id=config.PAYPAL_WEBHOOK_ID, webhook_event=event)
    verified = _call("POST", "/v1/notifications/verify-webhook-signature", json=payload)
    if verified.get("verification_status") != "SUCCESS":
        raise ValueError("Invalid PayPal webhook signature.")
    kind = event.get("event_type")
    resource = event.get("resource") or {}
    if kind == "CHECKOUT.ORDER.APPROVED":
        order_id = resource.get("id")
    elif kind == "PAYMENT.CAPTURE.COMPLETED":
        order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
    else:
        return {"ignored": True}
    order_id = _id(order_id)
    if not store.store.get(_path(order_id)):
        return {"ignored": True}
    return settle(order_id, capture=kind == "CHECKOUT.ORDER.APPROVED")
