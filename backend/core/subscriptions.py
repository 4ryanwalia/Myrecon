"""Recurring Pro billing. Provider records, never browser claims, grant access.

One active subscription per account; trial consumption and period credits are
atomic with the user's entitlement. Legacy packs are intentionally separate.
"""
import calendar
import json
from pathlib import Path
import hashlib
import re
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlsplit

import config
from core import paypal, razorpay, store

TRIAL_DAYS = 3
TRIAL_SCANS = 3
CATALOG = {
    "monthly": {"amount": 399, "currency": "USD", "interval": "MONTH", "scans": 10},
    "yearly": {"amount": 1999, "currency": "USD", "interval": "YEAR", "scans": 120},
    "inr_monthly": {"amount": 29900, "currency": "INR", "interval": "MONTH", "scans": 10},
    "inr_yearly": {"amount": 199900, "currency": "INR", "interval": "YEAR", "scans": 120},
}
TERMINAL = {"cancelled", "expired", "completed"}
BASE_URL = "https://www.myrecon.xyz/pricing"
# Razorpay limits a schedule to 100 years; both plans disclose a ten-year schedule.
RAZORPAY_TOTAL_COUNT = {"MONTH": 120, "YEAR": 10}
RAZORPAY_PERIOD = {"MONTH": "monthly", "YEAR": "yearly"}


def provider_for(key):
    return "razorpay" if key.startswith("inr_") else "paypal"


def configured_plan(provider, key, trial=True):
    if provider == "razorpay":
        env = config.BASIC_RAZORPAY_YEARLY_PLAN_ID if key == "inr_yearly" else config.BASIC_RAZORPAY_MONTHLY_PLAN_ID
    else:
        env = getattr(config, "BASIC_PAYPAL_" + key.upper() + ("_TRIAL" if trial else "_PAID") + "_PLAN_ID")
    if env:
        return env
    catalog_file = Path(__file__).with_name("billing_catalog.json")
    catalog = json.loads(catalog_file.read_text()) if catalog_file.exists() else {}
    return catalog.get(_namespace(provider), {}).get(key + ("_trial" if trial else "_paid"), "")


def _razorpay_ready():
    return (razorpay.enabled() and store.persistent() and bool(config.RAZORPAY_WEBHOOK_SECRET)
            and (config.RAZORPAY_KEY_ID.startswith("rzp_live_") or config.DEV_TEST_ACCOUNT))


def enabled(provider, key=None):
    if provider == "paypal":
        return paypal.enabled() and all(configured_plan("paypal", k, trial) for k in ("monthly", "yearly") for trial in (True, False))
    if provider != "razorpay" or not _razorpay_ready():
        return False
    # Monthly must be pre-provisioned. Yearly may be provisioned on first use
    # from the server catalog (persistently cached) and is verified before use.
    return key == "inr_yearly" or bool(configured_plan("razorpay", "inr_monthly"))


def offers():
    return [{"id": key, **value, "trial_days": TRIAL_DAYS,
             "provider": provider_for(key),
             "enabled": enabled(provider_for(key), key)}
            for key, value in CATALOG.items()]


def _namespace(provider):
    account = config.PAYPAL_CLIENT_ID if provider == "paypal" else config.RAZORPAY_KEY_ID
    return provider + "_" + hashlib.sha256(account.encode()).hexdigest()[:16]


def _path(provider, sid):
    pattern = r"I-[A-Z0-9]{6,32}" if provider == "paypal" else r"sub_[A-Za-z0-9]{6,32}"
    if not isinstance(sid, str) or not re.fullmatch(pattern, sid):
        raise ValueError("Invalid subscription.")
    return "web/subscriptions/" + _namespace(provider) + "/" + sid


def _user(uid):
    return "web/users/" + uid


def _stamp(value):
    if not value:
        return 0
    if isinstance(value, (int, float)):
        return int(value * 1000)
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def _period_end(start, interval):
    dt = datetime.fromtimestamp(start / 1000, timezone.utc)
    year, month = dt.year, dt.month
    if interval == "YEAR":
        year += 1
    else:
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return int(dt.replace(year=year, month=month,
                          day=min(dt.day, calendar.monthrange(year, month)[1])).timestamp() * 1000)


def provision_plan(provider, key, trial):
    """Create immutable, server-priced provider plans, cached in persistent storage."""
    offer = CATALOG[key]
    path = "web/subscription_plans/" + _namespace(provider) + "/v1_" + key + ("_trial" if trial else "_paid")
    cached = store.store.get(path)
    if cached:
        return cached["id"]
    if provider == "paypal":
        product_path = "web/subscription_plans/" + _namespace(provider) + "/product"
        product = store.store.get(product_path)
        if not product:
            product = paypal._call("POST", "/v1/catalogs/products", request_id="myrecon-basic-v1",
                                   json={"name": "MyRecon Basic", "type": "SERVICE", "category": "SOFTWARE"})
            store.store.set(product_path, {"id": product["id"]})
        cycles = []
        if trial:
            cycles.append({"frequency": {"interval_unit": "DAY", "interval_count": 3},
                           "tenure_type": "TRIAL", "sequence": 1, "total_cycles": 1,
                           "pricing_scheme": {"fixed_price": {"value": "0", "currency_code": "USD"}}})
        cycles.append({"frequency": {"interval_unit": offer["interval"], "interval_count": 1},
                       "tenure_type": "REGULAR", "sequence": len(cycles) + 1, "total_cycles": 0,
                       "pricing_scheme": {"fixed_price": {"value": f'{offer["amount"] / 100:.2f}', "currency_code": "USD"}}})
        result = paypal._call("POST", "/v1/billing/plans",
                              request_id="basic-v1-" + key + ("-trial" if trial else "-paid"),
                              json={"product_id": product["id"], "name": "Basic " + key,
                                    "status": "ACTIVE", "billing_cycles": cycles,
                                    "payment_preferences": {"auto_bill_outstanding": False,
                                                            "payment_failure_threshold": 1}})
    else:
        result = razorpay._call("POST", "/plans", json={"period": RAZORPAY_PERIOD[offer["interval"]], "interval": 1,
                               "item": {"name": "MyRecon Pro " + RAZORPAY_PERIOD[offer["interval"]],
                                        "amount": offer["amount"], "currency": offer["currency"]},
                               "notes": {"catalog": key}})
    store.store.set(path, {"id": result["id"]})
    return result["id"]


def _approval_url(result):
    url = next((x.get("href", "") for x in result.get("links", []) if x.get("rel") == "approve"), "")
    parsed = urlsplit(url)
    host = "www.paypal.com" if config.PAYPAL_ENV == "live" else "www.sandbox.paypal.com"
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Subscription approval link unavailable. Check your account before trying again.")
    return url


def _plan(provider, key, trial):
    plan_id = configured_plan(provider, key, trial)
    if not plan_id and provider == "razorpay" and key == "inr_yearly":
        plan_id = provision_plan(provider, key, True)
    if not plan_id:
        raise ValueError("This subscription checkout is temporarily unavailable.")
    # Validate configured plans against the advertised offer before asking for consent.
    offer = CATALOG[key]
    if provider == "razorpay":
        plan = razorpay._call("GET", "/plans/" + plan_id)
        item = plan.get("item") or {}
        valid = (plan.get("period") == RAZORPAY_PERIOD[offer["interval"]] and plan.get("interval") == 1
                 and item.get("amount") == offer["amount"] and item.get("currency") == offer["currency"])
    else:
        plan = paypal._call("GET", "/v1/billing/plans/" + plan_id)
        cycles = plan.get("billing_cycles") or []
        regular = cycles[-1] if cycles else {}
        price = (regular.get("pricing_scheme") or {}).get("fixed_price") or {}
        valid = (plan.get("status") == "ACTIVE" and len(cycles) == (2 if trial else 1)
                 and regular.get("tenure_type") == "REGULAR" and regular.get("total_cycles") == 0
                 and regular.get("frequency") == {"interval_unit": offer["interval"], "interval_count": 1}
                 and price.get("currency_code") == "USD"
                 and Decimal(str(price.get("value", "-1"))) == Decimal(offer["amount"]) / 100
                 and Decimal(str((plan.get("payment_preferences", {}).get("setup_fee") or {}).get("value", "0"))) == 0
                 and not plan.get("taxes"))
        if trial:
            first = cycles[0] if cycles else {}
            cost = (first.get("pricing_scheme") or {}).get("fixed_price") or {}
            valid = valid and (first.get("tenure_type") == "TRIAL" and first.get("total_cycles") == 1
                               and first.get("frequency") == {"interval_unit": "DAY", "interval_count": 3}
                               and Decimal(str(cost.get("value", "0"))) == 0)
    if not valid or plan.get("id") != plan_id:
        raise ValueError("The provider plan does not match the advertised price. Contact support.")
    return plan_id


def _close_unauthorized_razorpay(uid, pending):
    """Cancel a Razorpay checkout the customer never authorized, so another can start.

    Only Razorpay "created" (no mandate, nothing charged) qualifies. PayPal
    APPROVAL_PENDING cannot be cancelled through the API, and a later approval
    of an abandoned link would bill without access, so it is never replaced.
    Returns True only when the provider confirms the old checkout is terminal.
    """
    sid = pending.get("id")
    # The stored status must already show "created" from a provider refresh;
    # anything else is rejected without contacting a provider.
    if pending.get("provider") != "razorpay" or not sid or pending.get("status") != "created":
        return False
    refreshed = sync("razorpay", sid, uid)
    if refreshed.get("status") in TERMINAL and not refreshed.get("active"):
        return True
    if refreshed.get("status") != "created" or refreshed.get("active"):
        return False
    try:
        razorpay._call("POST", "/subscriptions/" + sid + "/cancel", json={"cancel_at_cycle_end": False})
    except razorpay.RazorpayError:
        pass
    refreshed = sync("razorpay", sid, uid)
    if refreshed.get("status") not in TERMINAL or refreshed.get("active"):
        raise ValueError("Your unfinished Razorpay checkout could not be closed. Resume it, or try again shortly.")
    return True


def checkout(uid, key):
    if key not in CATALOG:
        raise ValueError("Unknown subscription plan.")
    provider = provider_for(key)
    if not enabled(provider, key):
        raise ValueError("This subscription checkout is temporarily unavailable.")
    existing = store.store.get(_user(uid)) or {}
    pending = existing.get("subscription") or {}
    if pending.get("id") and pending.get("plan") == key and pending.get("provider") == provider:
        refreshed = sync(provider, pending["id"], uid)
        if refreshed["status"] in ("pending", "approval_pending", "created"):
            intent = store.store.get(_path(provider, pending["id"]))
            return {"id": pending["id"], "provider": provider, "url": intent.get("url"),
                    "key_id": config.RAZORPAY_KEY_ID if provider == "razorpay" else None,
                    "trial": intent["trial"], "trial_until": intent.get("trial_until"), **CATALOG[key]}
    existing = store.store.get(_user(uid)) or {}
    pending = existing.get("subscription") or {}
    # An unauthorized Razorpay checkout for another plan or provider is closed
    # first; this is what lets a customer switch after abandoning Razorpay.
    if pending and pending.get("until", 0) <= time.time() * 1000 and _close_unauthorized_razorpay(uid, pending):
        existing = store.store.get(_user(uid)) or {}
        pending = existing.get("subscription") or {}
    # Reject an existing contract before making unrelated provider API calls.
    # The transaction below remains the final concurrency guard.
    if pending and (pending.get("status") not in TERMINAL or pending.get("until", 0) > time.time() * 1000):
        raise ValueError("You already have a subscription or pending checkout. Manage it below before starting another.")
    trial = not bool(existing.get("basic_trial_used"))
    plan_id = _plan(provider, key, trial)
    binding = uuid.uuid4().hex
    now = int(time.time() * 1000)
    def reserve(cur):
        cur = cur or {}
        sub = cur.get("subscription") or {}
        if sub and (sub.get("status") not in TERMINAL or sub.get("until", 0) > now):
            raise ValueError("You already have a subscription or pending checkout. Manage it below before starting another.")
        if bool(cur.get("basic_trial_used")) == trial:
            raise ValueError("Your trial eligibility changed. Refresh before subscribing.")
        cur["subscription"] = {"binding": binding, "provider": provider, "plan": key,
                               "status": "creating", "created": now, "until": 0,
                               "trial": not bool(cur.get("basic_trial_used"))}
        return cur
    record = store.store.transaction(_user(uid), reserve)
    intent = {**record["subscription"], "uid": uid}
    # On an ambiguous provider timeout retain the reservation: automatically
    # retrying a non-idempotent create could leave two billable subscriptions.
    intent["provider_plan"] = plan_id
    store.store.set("web/subscription_attempts/" + binding, intent)
    if provider == "paypal":
        result = paypal._call("POST", "/v1/billing/subscriptions", request_id=binding, json={
            "plan_id": plan_id, "custom_id": binding,
            "application_context": {"brand_name": "MyRecon", "shipping_preference": "NO_SHIPPING",
                                    "user_action": "SUBSCRIBE_NOW", "return_url": BASE_URL + "?subscription=return",
                                    "cancel_url": BASE_URL + "?subscription=cancel"}})
    else:
        payload = {"plan_id": plan_id, "total_count": RAZORPAY_TOTAL_COUNT[CATALOG[key]["interval"]], "quantity": 1,
                   "customer_notify": True, "notes": {"binding": binding}}
        if intent["trial"]:
            payload["start_at"] = int(time.time()) + TRIAL_DAYS * 86400
            intent["trial_until"] = payload["start_at"] * 1000
        result = razorpay._call("POST", "/subscriptions", json=payload)
    sid = result["id"]
    intent.update(id=sid, status="pending")
    store.store.set(_path(provider, sid), intent)
    def attach(cur):
        if (cur.get("subscription") or {}).get("binding") != binding:
            raise ValueError("Subscription reservation changed. Contact support.")
        cur["subscription"].update(id=sid, status="pending")
        return cur
    store.store.transaction(_user(uid), attach)
    url = _approval_url(result) if provider == "paypal" else None
    if url:
        store.store.transaction(_path(provider, sid), lambda cur: {**cur, "url": url})
    return {"id": sid, "provider": provider, "url": url,
            "key_id": config.RAZORPAY_KEY_ID if provider == "razorpay" else None,
            "trial": intent["trial"], "trial_until": intent.get("trial_until"), **CATALOG[key]}


def sync(provider, sid, uid=None):
    path = _path(provider, sid)
    intent = store.store.get(path)
    if not intent or (uid is not None and uid != intent["uid"]):
        raise ValueError("Subscription not found for this account.")
    observed = time.time_ns()
    remote = (paypal._call("GET", "/v1/billing/subscriptions/" + sid) if provider == "paypal"
              else razorpay._call("GET", "/subscriptions/" + sid))
    binding = remote.get("custom_id") if provider == "paypal" else (remote.get("notes") or {}).get("binding")
    if remote.get("id") != sid or remote.get("plan_id") != intent["provider_plan"] or binding != intent["binding"]:
        raise ValueError("Subscription details do not match this checkout.")
    status = str(remote.get("status", "unknown")).lower()
    offer = CATALOG[intent["plan"]]
    now = int(time.time() * 1000)
    until, period, count, trial_until = 0, None, 0, 0
    if provider == "paypal":
        billing = remote.get("billing_info") or {}
        payment = billing.get("last_payment") or {}
        amount = payment.get("amount") or {}
        paid_at = _stamp(payment.get("time"))
        paid = (paid_at and amount.get("currency_code") == "USD"
                and Decimal(str(amount.get("value", "0"))) == Decimal(offer["amount"]) / 100)
        if paid:
            until = _period_end(paid_at, offer["interval"])
            next_bill = _stamp(billing.get("next_billing_time"))
            if paid_at < next_bill <= until + 86400000:
                until = next_bill
            period, count = "paid:" + str(paid_at), offer["scans"]
        elif intent["trial"] and status == "active":
            start = _stamp(remote.get("start_time"))
            trial_until = start + TRIAL_DAYS * 86400000 if start else 0
            if start <= now < trial_until:
                until, period, count = trial_until, "trial", TRIAL_SCANS
    else:
        if int(remote.get("paid_count") or 0) > 0:
            start, end = _stamp(remote.get("current_start")), _stamp(remote.get("current_end"))
            if start and end and end <= _period_end(start, offer["interval"]) + 86400000:
                until, period, count = end, "paid:" + str(start), offer["scans"]
        elif intent["trial"] and status in ("authenticated", "active"):
            trial_until = intent.get("trial_until", 0)
            if now < trial_until:
                until, period, count = trial_until, "trial", TRIAL_SCANS

    def apply(cur):
        cur = cur or {}
        sub = cur.get("subscription") or {}
        if sub.get("id") != sid or sub.get("provider") != provider or sub.get("observed", 0) > observed:
            return cur
        # A cancellation is terminal, even when an older provider GET finishes late.
        if sub.get("status") in TERMINAL and status not in TERMINAL:
            return cur
        sub.update(status=status, observed=observed, checked_at=now)
        if period and until > now and status not in ("suspended", "halted", "expired"):
            if period == "trial" and cur.get("basic_trial_used") not in (None, sid):
                return cur
            if sub.get("period") != period and until > sub.get("until", 0):
                sub.update(period=period, scans_left=count, until=until)
            if intent["trial"]:
                cur["basic_trial_used"] = sid
            if period == "trial":
                sub["trial_until"] = trial_until
        if status in ("suspended", "halted", "expired"):
            sub["until"] = min(sub.get("until", 0), now)
        cur["subscription"] = sub
        return cur
    record = store.store.transaction(_user(intent["uid"]), apply)
    result = public(record)
    if result and provider == "paypal" and status == "approval_pending":
        result["approval_url"] = intent.get("url")
    return result


def public(record):
    sub = (record or {}).get("subscription") or {}
    if not sub:
        return None
    result = {key: sub.get(key) for key in ("id", "provider", "plan", "status", "until", "trial_until", "scans_left", "period")}
    result["active"] = sub.get("until", 0) > time.time() * 1000
    result["trial_eligible"] = not bool((record or {}).get("basic_trial_used"))
    return result


def current(uid, refresh=True):
    record = store.store.get(_user(uid)) or {}
    sub = record.get("subscription") or {}
    if refresh and sub.get("id") and sub.get("status") not in TERMINAL:
        return sync(sub["provider"], sub["id"], uid)
    return public(record)


def cancel(uid):
    sub = current(uid)
    if not sub or not sub.get("id"):
        raise ValueError("No cancellable subscription found. If checkout is still being prepared, contact support.")
    if sub["status"] in TERMINAL:
        return sub
    provider, sid = sub["provider"], sub["id"]
    if provider == "paypal" and sub["status"] == "approval_pending":
        raise ValueError("PayPal checkout has not been approved; no recurring payment is authorized. Resume the pending checkout to finish approval. Active subscriptions can be cancelled here.")
    if provider == "paypal":
        paypal._call("POST", "/v1/billing/subscriptions/" + sid + "/cancel",
                     json={"reason": "Cancelled by the account owner"})
    else:
        razorpay._call("POST", "/subscriptions/" + sid + "/cancel", json={"cancel_at_cycle_end": False})
    def mark(cur):
        if (cur.get("subscription") or {}).get("id") == sid:
            cur["subscription"]["status"] = "cancelled"
        return cur
    return public(store.store.transaction(_user(uid), mark))


def webhook(provider, event):
    """Called only AFTER existing provider signature verification."""
    if provider == "paypal":
        resource = event.get("resource") or {}
        sid = resource.get("billing_agreement_id") or (resource.get("id") if str(event.get("event_type", "")).startswith("BILLING.SUBSCRIPTION.") else None)
    else:
        sid = (((event.get("payload") or {}).get("subscription") or {}).get("entity") or {}).get("id")
    if not sid or not store.store.get(_path(provider, sid)):
        return {"ignored": True}
    result = sync(provider, sid)
    if provider == "paypal" and event.get("event_type") in ("PAYMENT.SALE.REFUNDED", "PAYMENT.SALE.REVERSED"):
        intent = store.store.get(_path(provider, sid))
        def revoke(cur):
            if (cur.get("subscription") or {}).get("id") == sid:
                cur["subscription"]["until"] = 0
            return cur
        result = public(store.store.transaction(_user(intent["uid"]), revoke))
    return {"subscription": result}


def register(app, require_user):
    from flask import request
    from core import responses

    @app.route("/api/billing/subscriptions", methods=["GET", "POST", "OPTIONS"])
    @app.route("/api/billing/subscriptions/cancel", methods=["POST", "OPTIONS"])
    def subscription_api():
        if request.method == "OPTIONS":
            return "", 204
        uid = require_user()["sub"]
        if not store.persistent():
            return responses.error("Accounts are unavailable.", status=503)
        try:
            if request.path.endswith("/cancel"):
                result = {"subscription": cancel(uid)}
            elif request.method == "GET":
                result = {"subscription": current(uid)}
            else:
                body = request.get_json(silent=True) or {}
                if not isinstance(body, dict) or body.get("consent") is not True:
                    raise ValueError("Please accept the recurring billing terms before continuing.")
                result = checkout(uid, body.get("plan"))
            response, status = responses.ok(result)
            response.headers["Cache-Control"] = "no-store"
            return response, status
        except ValueError as exc:
            return responses.error(str(exc), status=400)
        except (paypal.PayPalError, razorpay.RazorpayError):
            return responses.error("The payment provider is unavailable. Check subscription status before retrying; contact support if checkout remains pending.", status=502)
