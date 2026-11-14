"""
Owner notification dispatcher for subscriptions, trials, and payments.

Sends:
1. Email alerts via SMTP (Gmail, Brevo, SendGrid, Mailgun, Amazon SES, or custom).
2. Optional instant Webhook alerts (Discord, Slack, Telegram, n8n, Zapier).

All outbound notifications run in non-blocking background threads so provider
webhooks and client checkout requests are never delayed.
"""

from __future__ import annotations

import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import json
import logging
import smtplib
import threading
from typing import Optional

import requests

import config

log = logging.getLogger("myrecon.notifications")


def _format_money(amount: int, currency: str) -> str:
    curr = (currency or "USD").upper()
    val = amount / 100.0
    if curr == "USD":
        return f"${val:.2f} USD"
    if curr == "INR":
        return f"₹{val:.2f} INR"
    return f"{val:.2f} {curr}"


def _format_time(timestamp_ms: Optional[int]) -> str:
    if not timestamp_ms:
        return "N/A"
    try:
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000, datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(timestamp_ms)


def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> bool:
    """Send an email using configured SMTP settings. Safe and non-raising."""
    recipient = to_email or config.NOTIFICATION_EMAIL_TO
    if not recipient:
        log.info("No notification recipient configured. Skipping email: %s", subject)
        return False

    if not config.SMTP_HOST:
        log.info(
            "[EMAIL NOTIFICATION (SMTP not configured)]\nTo: %s\nSubject: %s\n\n%s",
            recipient,
            subject,
            text_body,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config.SMTP_FROM or config.SMTP_USER or recipient
        msg["To"] = recipient
        msg["Date"] = formatdate(localtime=False)

        part_text = MIMEText(text_body, "plain", "utf-8")
        msg.attach(part_text)

        if html_body:
            part_html = MIMEText(html_body, "html", "utf-8")
            msg.attach(part_html)

        if config.SMTP_USE_SSL or config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
            if config.SMTP_USE_TLS:
                server.starttls()

        if config.SMTP_USER and config.SMTP_PASSWORD:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)

        server.send_message(msg)
        server.quit()
        log.info("Email notification successfully sent to %s: %s", recipient, subject)
        return True
    except Exception as exc:
        log.error("Failed to send email notification to %s: %s", recipient, exc)
        return False


def send_webhook(
    title: str,
    message: str,
    fields: Optional[dict] = None,
) -> bool:
    """Send alert to an optional webhook URL (Discord/Slack/Zapier/custom)."""
    url = config.NOTIFICATION_WEBHOOK_URL
    if not url:
        return False

    try:
        # Compatible with Slack/Discord incoming webhook formats
        payload = {
            "text": f"*{title}*\n{message}",
            "content": f"**{title}**\n{message}",
            "attachments": [
                {
                    "title": title,
                    "text": message,
                    "fields": [
                        {"title": k, "value": str(v), "short": True}
                        for k, v in (fields or {}).items()
                    ],
                }
            ],
        }
        res = requests.post(url, json=payload, timeout=8)
        return res.status_code in (200, 204)
    except Exception as exc:
        log.warning("Failed to send webhook notification: %s", exc)
        return False


ASYNC_DISPATCH = True


def _dispatch_async(fn, *args, **kwargs) -> threading.Thread:
    """Run notification dispatch in a background thread."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


def _dispatch(fn, *args, **kwargs):
    if ASYNC_DISPATCH:
        return _dispatch_async(fn, *args, **kwargs)
    return fn(*args, **kwargs)


def _send_all(subject: str, text_body: str, html_body: Optional[str] = None, fields: Optional[dict] = None):
    send_email(config.NOTIFICATION_EMAIL_TO, subject, text_body, html_body)
    send_webhook(subject, text_body, fields)


# ── Notification Templates ──────────────────────────────────────────
#
# Alerts tell the owner THAT something happened, never WHO. They carry no
# customer email, user ID or subscription ID, so an alert forwarded to a
# webhook (Discord, Slack, Zapier) discloses nothing about a subscriber.
# Look a subscriber up in the payment provider's dashboard when needed.

def _html(badge: str, colour: str, heading: str, rows: list, stats: list) -> str:
    cell = "padding:8px 12px;border-bottom:1px solid #334155;font-size:14px;color:#cbd5e1"
    table = "".join(f'<tr><td style="{cell};font-weight:600;color:#94a3b8;width:40%">{k}</td><td style="{cell}">{v}</td></tr>' for k, v in rows)
    figures = "".join(f'<div style="font-size:13px;color:#cbd5e1;margin-bottom:6px">{k}: <b style="color:{colour}">{v}</b></div>' for k, v in stats)
    return (
        '<!DOCTYPE html><html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0f172a;color:#f8fafc;margin:0;padding:24px">'
        f'<div style="background:#1e293b;border-radius:8px;padding:24px;max-width:600px;margin:0 auto;border:1px solid {colour}">'
        f'<span style="background:{colour};color:#000;padding:4px 10px;border-radius:9999px;font-size:12px;font-weight:bold;text-transform:uppercase">{badge}</span>'
        f'<h2 style="color:{colour};margin:12px 0 8px">{heading}</h2>'
        f'<table style="width:100%;border-collapse:collapse;margin:16px 0 20px">{table}</table>'
        f'<div style="background:#0f172a;border-radius:6px;padding:16px;border-left:4px solid {colour}">{figures}</div>'
        '</div></body></html>'
    )


def _text(intro: str, rows: list, stats: list) -> str:
    lines = [intro, ""] + [f"{k}: {v}" for k, v in rows] + ["", "--- Trial totals ---"] + [f"{k}: {v}" for k, v in stats]
    return "\n".join(lines) + "\n"


def _plan(trial: dict) -> tuple:
    return trial.get("plan", "monthly"), (trial.get("provider") or "").upper()


def dispatch_trial_started(trial: dict, summary: dict):
    """Notify the owner that someone started a 3-day trial."""
    plan, provider = _plan(trial)
    rows = [("Plan", plan), ("Provider", provider),
            ("Trial Started", _format_time(trial.get("trial_started_at"))),
            ("Trial Ends", _format_time(trial.get("trial_until")))]
    stats = [("Total Trials Started", summary.get("total_trials_started", 1)),
             ("Active Trials", summary.get("active_trials", 1)),
             ("Converted to Paid", summary.get("trials_converted_to_paid", 0)),
             ("Conversion Rate", summary.get("conversion_rate_display", "0.0%"))]
    subject = f"🚀 [MyRecon] New 3-Day Free Trial Started ({plan}, {provider})"
    _dispatch(_send_all, subject, _text("Someone just started a 3-day free trial on MyRecon.", rows, stats),
              _html("3-Day Trial", "#38bdf8", "🚀 New trial started", rows, stats), dict(rows + stats))


def dispatch_trial_converted(trial: dict, summary: dict):
    """Notify the owner that a trial converted to a paid subscription."""
    plan, provider = _plan(trial)
    money = _format_money(trial.get("amount", 0), trial.get("currency", "USD"))
    rows = [("Amount Received", money), ("Plan", plan), ("Provider", provider),
            ("Converted At", _format_time(trial.get("converted_at")))]
    stats = [("Total Trials Started", summary.get("total_trials_started", 1)),
             ("Converted to Paid", summary.get("trials_converted_to_paid", 1)),
             ("Cancelled Before End", summary.get("trials_cancelled_before_end", 0)),
             ("Conversion Rate", summary.get("conversion_rate_display", "100.0%"))]
    subject = f"💰 [MyRecon] Money Received! Trial Converted: {money}"
    _dispatch(_send_all, subject, _text("A 3-day trial just converted to a paid subscription.", rows, stats),
              _html("Payment Received", "#34d399", "💰 Trial converted to paid", rows, stats), dict(rows + stats))


def dispatch_trial_cancelled(trial: dict, summary: dict):
    """Notify the owner that a trial was cancelled before it ended."""
    plan, provider = _plan(trial)
    rows = [("Plan", plan), ("Provider", provider),
            ("Cancelled At", _format_time(trial.get("cancelled_at"))),
            ("Reason", trial.get("cancel_reason") or "User request")]
    stats = [("Total Trials Started", summary.get("total_trials_started", 1)),
             ("Cancelled Before End", summary.get("trials_cancelled_before_end", 1)),
             ("Converted to Paid", summary.get("trials_converted_to_paid", 0)),
             ("Cancellation Rate", summary.get("cancellation_rate_display", "0.0%")),
             ("Conversion Rate", summary.get("conversion_rate_display", "0.0%"))]
    subject = f"⚠️ [MyRecon] 3-Day Trial Cancelled ({plan}, {provider})"
    _dispatch(_send_all, subject, _text("A 3-day trial was cancelled before it ended.", rows, stats),
              _html("Trial Cancelled", "#fbbf24", "⚠️ Trial cancelled", rows, stats), dict(rows + stats))
