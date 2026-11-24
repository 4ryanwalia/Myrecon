"""
Tests for free trial tracking, conversion metrics, notifications, and analytics endpoint.
"""

from datetime import datetime, timezone
import json
import pytest

import config
from core import notifications, paypal, plans, razorpay, store, subscriptions as sub, trial_tracking

NOW = 1794432000
SID = "I-TRIAL123456"
UID = "trial-test-user"
USER_EMAIL = "subscriber@example.com"


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    mem = store._MemoryStore()
    monkeypatch.setattr(store, "store", mem)
    monkeypatch.setattr(plans, "store", mem)
    monkeypatch.setattr(store, "persistent", lambda: True)
    monkeypatch.setattr(sub.time, "time", lambda: NOW)
    monkeypatch.setattr(trial_tracking.time, "time", lambda: NOW)
    monkeypatch.setattr(plans, "_now_ms", lambda: NOW * 1000)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", True)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(notifications, "ASYNC_DISPATCH", False)  # Synchronous for deterministic tests

    # Set mock configurations
    for name, value in {
        "PAYPAL_CLIENT_ID": "client",
        "PAYPAL_CLIENT_SECRET": "secret",
        "PAYPAL_WEBHOOK_ID": "webhook",
        "PAYPAL_ENV": "sandbox",
        "RAZORPAY_KEY_ID": "rzp_test_key",
        "RAZORPAY_KEY_SECRET": "secret",
        "RAZORPAY_WEBHOOK_SECRET": "hook",
        "BASIC_RAZORPAY_MONTHLY_PLAN_ID": "plan_basic",
        "NOTIFICATION_EMAIL_TO": "owner@myrecon.xyz",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": 587,
        "SMTP_USER": "mailer@myrecon.xyz",
        "SMTP_PASSWORD": "secretpassword",
        "TRIAL_ANALYTICS_TOKEN": "secret-analytics-token",
    }.items():
        monkeypatch.setattr(config, name, value)

    for key in ("MONTHLY_TRIAL", "YEARLY_TRIAL", "MONTHLY_PAID", "YEARLY_PAID"):
        monkeypatch.setattr(config, "BASIC_PAYPAL_" + key + "_PLAN_ID", "P-" + key)


def seed_trial(provider="paypal", plan="monthly", email=USER_EMAIL):
    sid = SID if provider == "paypal" else "sub_TR123456"
    record = {
        "id": sid,
        "provider": provider,
        "plan": plan,
        "trial": True,
        "status": "pending",
        "binding": "binding",
        "until": 0,
        "trial_until": (NOW + 3 * 86400) * 1000,
        "email": email,
    }
    store.store.set(sub._user(UID), {"subscription": record, "email": email})
    store.store.set(sub._path(provider, sid), {**record, "uid": UID, "provider_plan": "provider-plan"})
    return sid


def remote_sub(status="ACTIVE", paid=False, amount="3.99"):
    return {
        "id": SID,
        "plan_id": "provider-plan",
        "custom_id": "binding",
        "status": status,
        "start_time": iso(NOW),
        "subscriber": {"email_address": USER_EMAIL},
        "billing_info": {
            "last_payment": {"time": iso(NOW), "amount": {"currency_code": "USD", "value": amount}} if paid else {},
            "next_billing_time": iso(NOW + (30 if paid else 3) * 86400),
        },
    }


def test_metrics_calculation_math():
    summary = {
        "total_trials_started": 10,
        "active_trials": 2,
        "trials_converted_to_paid": 5,
        "trials_cancelled_before_end": 3,
        "trials_expired_unconverted": 0,
    }
    metrics = trial_tracking.calculate_metrics(summary)
    assert metrics["total_trials_started"] == 10
    assert metrics["active_trials"] == 2
    assert metrics["trials_converted_to_paid"] == 5
    assert metrics["trials_cancelled_before_end"] == 3
    assert metrics["conversion_rate_percent"] == 50.0
    assert metrics["conversion_rate_display"] == "50.0%"
    assert metrics["decided_trials"] == 8
    assert metrics["decided_conversion_rate_percent"] == 62.5
    assert metrics["cancellation_rate_percent"] == 30.0


def test_metrics_calculation_zero_safe():
    metrics = trial_tracking.calculate_metrics({})
    assert metrics["total_trials_started"] == 0
    assert metrics["conversion_rate_percent"] == 0.0
    assert metrics["decided_conversion_rate_percent"] == 0.0
    assert metrics["cancellation_rate_percent"] == 0.0


def test_trial_start_records_and_dispatches_notification(monkeypatch):
    sid = seed_trial()
    dispatched = []
    monkeypatch.setattr(notifications, "send_email", lambda *a, **k: dispatched.append(("email", a)) or True)

    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote_sub("ACTIVE", paid=False))
    res = sub.sync("paypal", sid, UID)
    assert res["active"]
    assert res["period"] == "trial"

    summary = trial_tracking.get_summary()
    assert summary["total_trials_started"] == 1
    assert summary["active_trials"] == 1
    assert summary["trials_converted_to_paid"] == 0

    # Ensure email notification was dispatched with correct subject & content
    assert len(dispatched) == 1
    call_args = dispatched[0][1]
    to_email, subject, text_body = call_args[0], call_args[1], call_args[2]
    assert to_email == "owner@myrecon.xyz"
    assert "New Free Trial Started" in subject
    # Alerts say that a trial started, never who started it.
    assert USER_EMAIL not in subject and USER_EMAIL not in text_body and UID not in text_body
    assert sid not in text_body and USER_EMAIL not in call_args[3]
    assert "Plan: monthly" in text_body
    assert "PAYPAL" in text_body

    # Second sync should be idempotent (no duplicate email or double count)
    sub.sync("paypal", sid, UID)
    summary_again = trial_tracking.get_summary()
    assert summary_again["total_trials_started"] == 1
    assert len(dispatched) == 1


def test_trial_converted_to_paid_records_and_dispatches_notification(monkeypatch):
    sid = seed_trial()
    dispatched = []
    monkeypatch.setattr(notifications, "send_email", lambda *a, **k: dispatched.append(("email", a)) or True)

    # 1. Trial starts
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote_sub("ACTIVE", paid=False))
    sub.sync("paypal", sid, UID)
    assert len(dispatched) == 1
    assert "New Free Trial Started" in dispatched[0][1][1]

    # 2. Trial converts to paid (first payment captured after 3 days)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote_sub("ACTIVE", paid=True, amount="3.99"))
    res = sub.sync("paypal", sid, UID)
    assert res["active"]
    assert str(res["period"]).startswith("paid:")

    summary = trial_tracking.get_summary()
    assert summary["total_trials_started"] == 1
    assert summary["active_trials"] == 0
    assert summary["trials_converted_to_paid"] == 1
    assert summary["conversion_rate_percent"] == 100.0

    assert len(dispatched) == 2
    conv_email = dispatched[1][1]
    assert "Money Received! Trial Converted" in conv_email[1]
    assert "$3.99 USD" in conv_email[1]
    assert USER_EMAIL not in conv_email[1] and USER_EMAIL not in conv_email[2] and UID not in conv_email[2]
    assert "Conversion Rate: 100.0%" in conv_email[2]

    # Repeated sync does not re-notify or increment
    sub.sync("paypal", sid, UID)
    assert len(dispatched) == 2
    assert trial_tracking.get_summary()["trials_converted_to_paid"] == 1


def test_trial_cancelled_before_end(monkeypatch):
    sid = seed_trial()
    dispatched = []
    monkeypatch.setattr(notifications, "send_email", lambda *a, **k: dispatched.append(("email", a)) or True)

    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote_sub("ACTIVE", paid=False))
    sub.sync("paypal", sid, UID)
    assert len(dispatched) == 1

    # User cancels trial
    monkeypatch.setattr(paypal, "_call", lambda method, path, **kw: remote_sub("CANCELLED") if method == "GET" else {})
    cancel_res = sub.cancel(UID)
    assert cancel_res["status"] == "cancelled"

    summary = trial_tracking.get_summary()
    assert summary["total_trials_started"] == 1
    assert summary["active_trials"] == 0
    assert summary["trials_cancelled_before_end"] == 1
    assert summary["cancellation_rate_percent"] == 100.0
    assert summary["trials_converted_to_paid"] == 0

    assert len(dispatched) == 2
    canc_email = dispatched[1][1]
    assert "Trial Cancelled" in canc_email[1]
    assert USER_EMAIL not in canc_email[1] and USER_EMAIL not in canc_email[2] and UID not in canc_email[2]
    assert "Cancellation Rate: 100.0%" in canc_email[2]


def test_webhook_alert_carries_no_customer_details(monkeypatch):
    sid = seed_trial()
    posted = []
    monkeypatch.setattr(notifications.config, "NOTIFICATION_WEBHOOK_URL", "https://hooks.example.test/x")
    monkeypatch.setattr(notifications.requests, "post", lambda url, json=None, **k: posted.append(json) or type("R", (), {"status_code": 204})())
    monkeypatch.setattr(notifications, "send_email", lambda *a, **k: True)
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote_sub("ACTIVE", paid=False))
    sub.sync("paypal", sid, UID)
    assert len(posted) == 1
    body = str(posted[0])
    assert "New Free Trial Started" in body
    assert USER_EMAIL not in body and UID not in body and sid not in body


def test_sender_never_defaults_to_the_dmarc_protected_domain(monkeypatch):
    sent = []
    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): sent.append(msg)
        def quit(self): pass
    monkeypatch.setattr(notifications.config, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(notifications.config, "SMTP_FROM", "")
    monkeypatch.setattr(notifications.config, "SMTP_USER", "")
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    assert notifications.send_email("owner@example.test", "Subject", "Body")
    assert sent[0]["From"] == "owner@example.test"


def test_analytics_api_endpoint(monkeypatch):
    import app as app_module
    client = app_module.create_app().test_client()

    seed_trial()
    monkeypatch.setattr(paypal, "_call", lambda *a, **k: remote_sub("ACTIVE", paid=False))
    sub.sync("paypal", SID, UID)

    # 1. Dev test account access allowed
    resp = client.get("/api/billing/analytics/trials")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "summary" in data
    assert data["summary"]["total_trials_started"] == 1
    assert len(data["recent_trials"]) == 1
    assert data["recent_trials"][0]["subscription_id"] == SID

    # 2. Production mode without token or credentials rejects
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", False)
    resp_unauth = client.get("/api/billing/analytics/trials")
    assert resp_unauth.status_code == 403

    # 3. Access with valid admin token
    resp_token = client.get("/api/billing/analytics/trials", headers={"X-Admin-Token": "secret-analytics-token"})
    assert resp_token.status_code == 200
    assert resp_token.get_json()["summary"]["total_trials_started"] == 1

    # 4. Access with query token
    resp_query = client.get("/api/billing/analytics/trials?token=secret-analytics-token")
    assert resp_query.status_code == 200


def test_smtp_send_email_graceful_without_smtp(monkeypatch):
    # When SMTP_HOST is not set, send_email should log and return False without raising
    monkeypatch.setattr(config, "SMTP_HOST", "")
    ok = notifications.send_email("recipient@example.com", "Test Subject", "Hello body")
    assert ok is False
