"""
Razorpay: one-time orders for Pro passes, plus signature checks.

Flow:
  1. /api/billing/order    server creates an order with notes {uid, plan}
  2. browser opens Razorpay Checkout for that order
  3. /api/billing/verify   browser posts the payment id + signature back;
                           the signature proves Razorpay saw the payment
  4. /api/billing/webhook  Razorpay tells us independently (covers a closed tab)

Steps 3 and 4 both end in plans.grant_pass keyed on the order id, so whichever
lands first applies the pass and the other is a no-op. Who gets the pass is
always read from the order's notes, which only this server writes, never from
anything the browser sends.

Keys come from the environment. The key id is public (Checkout needs it); the
key secret and webhook secret never leave the server.
"""

import hashlib
import hmac

import requests

import config

_API = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    """Razorpay failed or was unreachable."""


class RazorpayAuthError(RazorpayError):
    """Razorpay refused our key id / secret."""


def enabled() -> bool:
    return bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


def _auth():
    return (config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)


def _call(method: str, path: str, **kwargs) -> dict:
    try:
        resp = requests.request(method, f"{_API}{path}", auth=_auth(), timeout=15, **kwargs)
    except requests.RequestException as exc:
        raise RazorpayError(f"unreachable: {exc.__class__.__name__}") from None
    if resp.status_code == 401:
        raise RazorpayAuthError("authentication failed")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", {}).get("description", "")
        except ValueError:
            detail = ""
        raise RazorpayError(f"HTTP {resp.status_code} {detail}".strip())
    return resp.json()


def create_order(amount_paise: int, receipt: str, notes: dict) -> dict:
    return _call("POST", "/orders", json={
        "amount": amount_paise, "currency": "INR",
        "receipt": receipt[:40], "notes": notes,
    })


def fetch_order(order_id: str) -> dict:
    return _call("GET", f"/orders/{order_id}")


def _hmac(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def payment_signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    expected = _hmac(config.RAZORPAY_KEY_SECRET, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature or "")


def webhook_signature_ok(body: bytes, signature: str) -> bool:
    if not config.RAZORPAY_WEBHOOK_SECRET:
        return False
    return hmac.compare_digest(_hmac(config.RAZORPAY_WEBHOOK_SECRET, body), signature or "")
