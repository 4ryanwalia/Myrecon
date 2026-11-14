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
        msg["From"] = config.SMTP_FROM or config.SMTP_USER or f"notifications@{config.APP_DOMAIN}"
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

def dispatch_trial_started(trial: dict, summary: dict):
    """Notify owner when a user starts a 3-day trial."""
    email = trial.get("email") or "Unknown (signed in)"
    uid = trial.get("uid", "N/A")
    plan = trial.get("plan", "monthly")
    provider = (trial.get("provider") or "").upper()
    sid = trial.get("subscription_id", "N/A")
    start_time = _format_time(trial.get("trial_started_at"))
    end_time = _format_time(trial.get("trial_until"))

    total = summary.get("total_trials_started", 1)
    active = summary.get("active_trials", 1)
    converted = summary.get("trials_converted_to_paid", 0)
    conv_rate = summary.get("conversion_rate_display", "0.0%")

    subject = f"🚀 [MyRecon] New 3-Day Free Trial Started: {email}"

    text_body = f"""Hello,

A new user just subscribed for your 3-Day Free Trial on MyRecon!

--- User & Subscription Details ---
Customer: {email}
User ID: {uid}
Plan: {plan}
Provider: {provider}
Subscription ID: {sid}
Trial Started: {start_time}
Trial Ends: {end_time}

--- Current Trial Metrics ---
Total Trials Started: {total}
Active Trials: {active}
Converted to Paid: {converted}
Overall Conversion Rate: {conv_rate}

You can track your trial conversion analytics on your dashboard or via the API.
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
    .card {{ background-color: #1e293b; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; border: 1px solid #334155; }}
    .badge {{ background-color: #3b82f6; color: white; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    h2 {{ color: #38bdf8; margin-top: 12px; margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; margin-bottom: 20px; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #334155; font-size: 14px; color: #cbd5e1; }}
    td.label {{ font-weight: 600; color: #94a3b8; width: 40%; }}
    .stats-box {{ background-color: #0f172a; border-radius: 6px; padding: 16px; margin-top: 16px; border-left: 4px solid #38bdf8; }}
    .stat-item {{ display: flex; justify-content: space-between; font-size: 13px; color: #cbd5e1; margin-bottom: 6px; }}
    .stat-val {{ font-weight: bold; color: #38bdf8; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">3-Day Trial</span>
    <h2>🚀 New Trial Subscription Started!</h2>
    <p style="color: #94a3b8; font-size: 14px;">A new customer has initiated a 3-day free trial on MyRecon.</p>
    <table>
      <tr><td class="label">Customer Email:</td><td><strong>{email}</strong></td></tr>
      <tr><td class="label">User ID:</td><td><code>{uid}</code></td></tr>
      <tr><td class="label">Plan:</td><td>{plan}</td></tr>
      <tr><td class="label">Provider:</td><td>{provider}</td></tr>
      <tr><td class="label">Subscription ID:</td><td><code>{sid}</code></td></tr>
      <tr><td class="label">Trial Started:</td><td>{start_time}</td></tr>
      <tr><td class="label">Trial Ends:</td><td>{end_time}</td></tr>
    </table>
    <div class="stats-box">
      <div style="font-weight: bold; margin-bottom: 8px; color: #e2e8f0;">📊 Live Trial Tracking</div>
      <div class="stat-item"><span>Total Trials Ever:</span> <span class="stat-val">{total}</span></div>
      <div class="stat-item"><span>Active Trials:</span> <span class="stat-val">{active}</span></div>
      <div class="stat-item"><span>Converted to Paid:</span> <span class="stat-val">{converted}</span></div>
      <div class="stat-item"><span>Conversion Ratio:</span> <span class="stat-val">{conv_rate}</span></div>
    </div>
  </div>
</body>
</html>
"""
    _dispatch(_send_all, subject, text_body, html_body, {
        "Customer": email, "Plan": plan, "Provider": provider,
        "Trial Ends": end_time, "Total Trials": total, "Conversion Rate": conv_rate
    })


def dispatch_trial_converted(trial: dict, summary: dict):
    """Notify owner when a 3-day trial converts to paid (money received)."""
    email = trial.get("email") or "Unknown (signed in)"
    uid = trial.get("uid", "N/A")
    plan = trial.get("plan", "monthly")
    provider = (trial.get("provider") or "").upper()
    sid = trial.get("subscription_id", "N/A")
    conv_time = _format_time(trial.get("converted_at"))
    money_str = _format_money(trial.get("amount", 0), trial.get("currency", "USD"))

    total = summary.get("total_trials_started", 1)
    converted = summary.get("trials_converted_to_paid", 1)
    cancelled = summary.get("trials_cancelled_before_end", 0)
    conv_rate = summary.get("conversion_rate_display", "100.0%")
    decided_rate = summary.get("decided_conversion_rate_display", "100.0%")

    subject = f"💰 [MyRecon] Money Received! Trial Converted: {money_str} ({email})"

    text_body = f"""Great news!

A customer has successfully completed their 3-Day Free Trial and converted into a PAID subscription!

--- Payment & Subscription Details ---
Amount Received: {money_str}
Customer: {email}
User ID: {uid}
Plan: {plan}
Provider: {provider}
Subscription ID: {sid}
Converted At: {conv_time}

--- Trial Conversion Performance ---
Total Trials Started: {total}
Successfully Converted to Paid: {converted} 💰
Cancelled Before 3 Days: {cancelled}
Trial-to-Paid Conversion Rate: {conv_rate} (Decided: {decided_rate})
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
    .card {{ background-color: #1e293b; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; border: 1px solid #10b981; }}
    .badge {{ background-color: #10b981; color: white; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    h2 {{ color: #34d399; margin-top: 12px; margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; margin-bottom: 20px; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #334155; font-size: 14px; color: #cbd5e1; }}
    td.label {{ font-weight: 600; color: #94a3b8; width: 40%; }}
    .highlight {{ font-size: 20px; font-weight: bold; color: #34d399; }}
    .stats-box {{ background-color: #0f172a; border-radius: 6px; padding: 16px; margin-top: 16px; border-left: 4px solid #10b981; }}
    .stat-item {{ display: flex; justify-content: space-between; font-size: 13px; color: #cbd5e1; margin-bottom: 6px; }}
    .stat-val {{ font-weight: bold; color: #34d399; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Payment Received</span>
    <h2>💰 Trial Converted to Paid Subscription!</h2>
    <p style="color: #94a3b8; font-size: 14px;">Money received: a 3-day free trial has converted to paid.</p>
    <table>
      <tr><td class="label">Amount Received:</td><td class="highlight">{money_str}</td></tr>
      <tr><td class="label">Customer Email:</td><td><strong>{email}</strong></td></tr>
      <tr><td class="label">User ID:</td><td><code>{uid}</code></td></tr>
      <tr><td class="label">Plan:</td><td>{plan}</td></tr>
      <tr><td class="label">Provider:</td><td>{provider}</td></tr>
      <tr><td class="label">Subscription ID:</td><td><code>{sid}</code></td></tr>
      <tr><td class="label">Converted At:</td><td>{conv_time}</td></tr>
    </table>
    <div class="stats-box">
      <div style="font-weight: bold; margin-bottom: 8px; color: #e2e8f0;">📈 Conversion Performance</div>
      <div class="stat-item"><span>Total Trials:</span> <span class="stat-val">{total}</span></div>
      <div class="stat-item"><span>Converted to Paid:</span> <span class="stat-val">{converted} 💰</span></div>
      <div class="stat-item"><span>Cancelled Before End:</span> <span class="stat-val">{cancelled}</span></div>
      <div class="stat-item"><span>Overall Conversion Rate:</span> <span class="stat-val">{conv_rate}</span></div>
      <div class="stat-item"><span>Decided Conversion Rate:</span> <span class="stat-val">{decided_rate}</span></div>
    </div>
  </div>
</body>
</html>
"""
    _dispatch(_send_all, subject, text_body, html_body, {
        "Amount": money_str, "Customer": email, "Plan": plan,
        "Provider": provider, "Conversion Rate": conv_rate
    })


def dispatch_trial_cancelled(trial: dict, summary: dict):
    """Notify owner when a user cancels during their 3-day trial."""
    email = trial.get("email") or "Unknown (signed in)"
    uid = trial.get("uid", "N/A")
    plan = trial.get("plan", "monthly")
    provider = (trial.get("provider") or "").upper()
    sid = trial.get("subscription_id", "N/A")
    canc_time = _format_time(trial.get("cancelled_at"))
    reason = trial.get("cancel_reason") or "User request"

    total = summary.get("total_trials_started", 1)
    converted = summary.get("trials_converted_to_paid", 0)
    cancelled = summary.get("trials_cancelled_before_end", 1)
    canc_rate = summary.get("cancellation_rate_display", "0.0%")
    conv_rate = summary.get("conversion_rate_display", "0.0%")

    subject = f"⚠️ [MyRecon] 3-Day Trial Cancelled: {email}"

    text_body = f"""Notice:

A customer has cancelled their 3-day trial before the trial period ended.

--- Cancellation Details ---
Customer: {email}
User ID: {uid}
Plan: {plan}
Provider: {provider}
Subscription ID: {sid}
Cancelled At: {canc_time}
Reason: {reason}

--- Trial Performance Update ---
Total Trials Started: {total}
Cancelled Before End: {cancelled}
Converted to Paid: {converted}
Cancellation Rate: {canc_rate}
Current Conversion Rate: {conv_rate}
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
    .card {{ background-color: #1e293b; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; border: 1px solid #f59e0b; }}
    .badge {{ background-color: #f59e0b; color: black; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
    h2 {{ color: #fbbf24; margin-top: 12px; margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; margin-bottom: 20px; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #334155; font-size: 14px; color: #cbd5e1; }}
    td.label {{ font-weight: 600; color: #94a3b8; width: 40%; }}
    .stats-box {{ background-color: #0f172a; border-radius: 6px; padding: 16px; margin-top: 16px; border-left: 4px solid #f59e0b; }}
    .stat-item {{ display: flex; justify-content: space-between; font-size: 13px; color: #cbd5e1; margin-bottom: 6px; }}
    .stat-val {{ font-weight: bold; color: #fbbf24; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Trial Cancelled</span>
    <h2>⚠️ 3-Day Trial Cancelled Before End</h2>
    <p style="color: #94a3b8; font-size: 14px;">A customer cancelled before the 3-day trial period expired.</p>
    <table>
      <tr><td class="label">Customer Email:</td><td><strong>{email}</strong></td></tr>
      <tr><td class="label">User ID:</td><td><code>{uid}</code></td></tr>
      <tr><td class="label">Plan:</td><td>{plan}</td></tr>
      <tr><td class="label">Provider:</td><td>{provider}</td></tr>
      <tr><td class="label">Subscription ID:</td><td><code>{sid}</code></td></tr>
      <tr><td class="label">Cancelled At:</td><td>{canc_time}</td></tr>
      <tr><td class="label">Reason:</td><td>{reason}</td></tr>
    </table>
    <div class="stats-box">
      <div style="font-weight: bold; margin-bottom: 8px; color: #e2e8f0;">📊 Updated Trial Metrics</div>
      <div class="stat-item"><span>Total Trials:</span> <span class="stat-val">{total}</span></div>
      <div class="stat-item"><span>Cancelled Before End:</span> <span class="stat-val">{cancelled}</span></div>
      <div class="stat-item"><span>Converted to Paid:</span> <span class="stat-val">{converted}</span></div>
      <div class="stat-item"><span>Cancellation Rate:</span> <span class="stat-val">{canc_rate}</span></div>
      <div class="stat-item"><span>Conversion Rate:</span> <span class="stat-val">{conv_rate}</span></div>
    </div>
  </div>
</body>
</html>
"""
    _dispatch(_send_all, subject, text_body, html_body, {
        "Customer": email, "Plan": plan, "Provider": provider,
        "Cancelled At": canc_time, "Cancellation Rate": canc_rate
    })
