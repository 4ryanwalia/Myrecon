"""Signed Shop purchases, bound to a signed-in account by an activation code.

Schema: https://cdn.buymeacoffee.com/assets/integrations/bmc-webhooks-openapi.json
No redirect, customer email, or browser payment claim can grant a pack.
"""
import hashlib
import hmac
import re
import secrets
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import config
from core import plans, store

PRICE = Decimal("3.99")
_CODE = re.compile(r"MR-[0-9a-f]{32}")
_LIFETIME = 7 * 86400


def enabled():
    try:
        url = urlsplit(config.BUYMEACOFFEE_SHOP_URL)
        item_id = int(config.BUYMEACOFFEE_ITEM_ID)
        return bool(store.persistent() and config.BUYMEACOFFEE_WEBHOOK_SECRET
                    and item_id > 0 and url.scheme == "https"
                    and url.hostname in ("buymeacoffee.com", "www.buymeacoffee.com")
                    and not url.username and not url.password and url.port in (None, 443)
                    and re.fullmatch(r"/[^/]+/e/" + str(item_id) + r"/?", url.path))
    except ValueError:
        return False


def _path(code):
    return "web/bmc_checkouts/" + hashlib.sha256(code.encode()).hexdigest()


def checkout(uid):
    code = "MR-" + secrets.token_hex(16)
    now = int(time.time())
    store.store.set(_path(code), {"uid": uid, "created": now, "expires": now + _LIFETIME})
    return {"url": config.BUYMEACOFFEE_SHOP_URL, "activation_code": code,
            "amount": 399, "currency": "USD", "expires_at": now + _LIFETIME}


def payment_status(uid, code):
    """Read only this account's checkout, never infer payment from its tier."""
    if not isinstance(code, str) or not _CODE.fullmatch(code.strip()):
        raise ValueError("Invalid activation code.")
    intent = store.store.get(_path(code.strip()))
    if not isinstance(intent, dict) or intent.get("uid") != uid:
        return None
    state = "applied" if intent.get("applied") is True else (
        "expired" if int(time.time()) > intent["expires"] else "pending")
    return {"payment_status": state, "expires_at": intent["expires"]}


def signature_ok(raw, signature):
    secret = config.BUYMEACOFFEE_WEBHOOK_SECRET
    if not secret or not re.fullmatch(r"[0-9a-f]{64}", signature):
        return False
    return hmac.compare_digest(hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), signature)


def _money(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else Decimal(0)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def settle(event):
    """Return False for unrelated/unpaid/test purchases; retry storage failures.

    The global transaction pins each purchase to one UID before granting it.
    Per-user atomic markers in grant_pass prevent duplicate credits on retries.
    A code can be used again by its owner for a separate paid pack.
    """
    if not isinstance(event, dict) or event.get("live_mode") is not True:
        return False
    if event.get("type") not in ("extra_purchase.created", "extra_purchase.updated"):
        return False
    data = event.get("data")
    if not isinstance(data, dict) or data.get("status") != "succeeded" or data.get("refunded") != "false":
        return False
    if data.get("currency") != "USD" or _money(data.get("amount")) < PRICE:
        return False
    purchase = data.get("id")
    if type(purchase) is not int or purchase <= 0:
        return False
    extras = data.get("extras")
    if not isinstance(extras, list) or len(extras) != 1:
        return False
    item = extras[0]
    if not isinstance(item, dict) or str(item.get("id")) != config.BUYMEACOFFEE_ITEM_ID:
        return False
    if type(item.get("quantity")) is not int or item["quantity"] != 1:
        return False
    if item.get("currency") != "USD" or _money(item.get("amount")) < PRICE:
        return False
    answers = item.get("question_answers")
    if not isinstance(answers, list) or len(answers) != 1 or not isinstance(answers[0], str):
        return False
    code = answers[0].strip()
    if not _CODE.fullmatch(code):
        return False
    intent = store.store.get(_path(code))
    if not isinstance(intent, dict) or not intent.get("uid"):
        return False
    paid_at = data.get("created_at")
    if type(paid_at) is not int or not intent["created"] <= paid_at <= intent["expires"]:
        return False
    ref = "buymeacoffee:" + str(purchase)
    # A malformed retry with another user's code cannot redirect a purchase.
    checkout_path = _path(code)

    def bind(cur):
        if not cur:
            return {"uid": intent["uid"], "ref": ref, "checkout": checkout_path}
        # Older purchase records predate checkout status. Bind them when a
        # valid signed retry arrives, preserving their original owner.
        if cur.get("uid") == intent["uid"] and not cur.get("checkout"):
            return {**cur, "checkout": checkout_path}
        return cur

    owner = store.store.transaction("web/bmc_purchases/" + str(purchase), bind)
    if owner["uid"] != intent["uid"] or owner["checkout"] != checkout_path:
        return False
    granted = plans.grant_pass(owner["uid"], "extended", ref)
    if not granted:
        # A retry can arrive after the grant committed but before the checkout
        # marker did. Prove this exact payment was granted to this UID before
        # repairing status; an existing paid tier is not payment confirmation.
        ref_key = hashlib.sha256(ref.encode()).hexdigest()[:40]
        ledger = store.store.get("web/payments/" + ref_key)
        if not isinstance(ledger, dict) or ledger.get("uid") != owner["uid"] or (
                ledger.get("ref") != ref or ledger.get("plan") != "extended"):
            return False

    def mark_applied(cur):
        if not isinstance(cur, dict) or cur.get("uid") != owner["uid"]:
            raise RuntimeError("Checkout changed before payment confirmation.")
        return {**cur, "applied": True}

    store.store.transaction(checkout_path, mark_applied)
    return True
