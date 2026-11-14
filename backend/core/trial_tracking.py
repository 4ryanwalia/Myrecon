"""
Trial tracking & conversion analytics for 3-day free trials.

Tracks:
1. Total users subscribing for a 3-day trial
2. Active trials currently in flight
3. Cancellations before the 3-day trial ends
4. Trial conversions into paid subscriptions (money received)
5. Conversion ratio and cancellation ratio
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Tuple

from core import store

log = logging.getLogger("myrecon.trials")

PATH_SUMMARY = "web/analytics/trial_summary"
PREFIX_TRIALS = "web/analytics/trials"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _trial_key(provider: str, sid: str) -> str:
    clean_sid = sid.replace("/", "_").replace(".", "_")
    return f"{provider}_{clean_sid}"


def _trial_path(provider: str, sid: str) -> str:
    return f"{PREFIX_TRIALS}/{_trial_key(provider, sid)}"


def calculate_metrics(summary: Optional[dict]) -> dict:
    summary = summary or {}
    total = int(summary.get("total_trials_started", 0))
    active = int(summary.get("active_trials", 0))
    converted = int(summary.get("trials_converted_to_paid", 0))
    cancelled = int(summary.get("trials_cancelled_before_end", 0))
    expired = int(summary.get("trials_expired_unconverted", 0))

    decided = converted + cancelled + expired

    conv_rate = round((converted / total * 100), 2) if total > 0 else 0.0
    decided_conv_rate = round((converted / decided * 100), 2) if decided > 0 else 0.0
    canc_rate = round((cancelled / total * 100), 2) if total > 0 else 0.0

    return {
        "total_trials_started": total,
        "active_trials": active,
        "trials_converted_to_paid": converted,
        "trials_cancelled_before_end": cancelled,
        "trials_expired_unconverted": expired,
        "decided_trials": decided,
        "conversion_rate_percent": conv_rate,
        "conversion_rate_display": f"{conv_rate:.1f}%",
        "decided_conversion_rate_percent": decided_conv_rate,
        "decided_conversion_rate_display": f"{decided_conv_rate:.1f}%",
        "cancellation_rate_percent": canc_rate,
        "cancellation_rate_display": f"{canc_rate:.1f}%",
        "last_updated": summary.get("last_updated", _now_ms()),
    }


def get_summary() -> dict:
    raw = store.store.get(PATH_SUMMARY) or {}
    return calculate_metrics(raw)


def record_trial_started(
    provider: str,
    sid: str,
    uid: str,
    plan: str,
    email: str = "",
    trial_until: int = 0,
) -> Tuple[dict, bool]:
    """Record a newly started 3-day trial. Idempotent: returns (record, is_new)."""
    now = _now_ms()
    path = _trial_path(provider, sid)
    existing = store.store.get(path)

    if existing and existing.get("status") in (
        "active_trial",
        "converted_to_paid",
        "cancelled_before_end",
        "expired_unconverted",
    ):
        return existing, False

    record = {
        "subscription_id": sid,
        "provider": provider,
        "uid": uid,
        "email": email or (existing or {}).get("email", ""),
        "plan": plan,
        "status": "active_trial",
        "trial_started_at": now,
        "trial_until": trial_until or (now + 3 * 86400000),
        "created_at": (existing or {}).get("created_at", now),
        "updated_at": now,
    }
    store.store.set(path, record)

    def update_summary(cur):
        cur = cur or {}
        cur["total_trials_started"] = int(cur.get("total_trials_started", 0)) + 1
        cur["active_trials"] = int(cur.get("active_trials", 0)) + 1
        cur["last_updated"] = now
        return cur

    store.store.transaction(PATH_SUMMARY, update_summary)
    log.info("Recorded 3-day trial started for %s (%s, %s)", sid, email or uid, plan)
    return record, True


def record_trial_converted(
    provider: str,
    sid: str,
    amount: int = 0,
    currency: str = "",
    email: str = "",
) -> Tuple[dict, bool]:
    """Record conversion of a trial to a paid subscription. Idempotent."""
    now = _now_ms()
    path = _trial_path(provider, sid)
    existing = store.store.get(path) or {}

    if existing.get("status") == "converted_to_paid":
        return existing, False

    was_active = existing.get("status") == "active_trial" or not existing

    record = {
        **existing,
        "subscription_id": sid,
        "provider": provider,
        "email": email or existing.get("email", ""),
        "status": "converted_to_paid",
        "converted_at": now,
        "amount": amount or existing.get("amount", 0),
        "currency": currency or existing.get("currency", "USD"),
        "updated_at": now,
    }
    store.store.set(path, record)

    def update_summary(cur):
        cur = cur or {}
        cur["trials_converted_to_paid"] = int(cur.get("trials_converted_to_paid", 0)) + 1
        if was_active:
            cur["active_trials"] = max(0, int(cur.get("active_trials", 0)) - 1)
        cur["last_updated"] = now
        return cur

    store.store.transaction(PATH_SUMMARY, update_summary)
    log.info("Recorded trial converted to paid for %s (%s %s)", sid, amount, currency)
    return record, True


def record_trial_cancelled(
    provider: str,
    sid: str,
    reason: str = "",
) -> Tuple[dict, bool]:
    """Record cancellation of a trial before the 3-day period ends. Idempotent."""
    now = _now_ms()
    path = _trial_path(provider, sid)
    existing = store.store.get(path) or {}

    if existing.get("status") in ("converted_to_paid", "cancelled_before_end"):
        return existing, False

    was_active = existing.get("status") == "active_trial" or not existing

    record = {
        **existing,
        "subscription_id": sid,
        "provider": provider,
        "status": "cancelled_before_end",
        "cancelled_at": now,
        "cancel_reason": reason,
        "updated_at": now,
    }
    store.store.set(path, record)

    def update_summary(cur):
        cur = cur or {}
        cur["trials_cancelled_before_end"] = int(cur.get("trials_cancelled_before_end", 0)) + 1
        if was_active:
            cur["active_trials"] = max(0, int(cur.get("active_trials", 0)) - 1)
        cur["last_updated"] = now
        return cur

    store.store.transaction(PATH_SUMMARY, update_summary)
    log.info("Recorded trial cancelled before end for %s (%s)", sid, reason)
    return record, True


def record_trial_expired(
    provider: str,
    sid: str,
) -> Tuple[dict, bool]:
    """Record trial expired without payment or cancellation. Idempotent."""
    now = _now_ms()
    path = _trial_path(provider, sid)
    existing = store.store.get(path) or {}

    if existing.get("status") in ("converted_to_paid", "cancelled_before_end", "expired_unconverted"):
        return existing, False

    was_active = existing.get("status") == "active_trial" or not existing

    record = {
        **existing,
        "subscription_id": sid,
        "provider": provider,
        "status": "expired_unconverted",
        "expired_at": now,
        "updated_at": now,
    }
    store.store.set(path, record)

    def update_summary(cur):
        cur = cur or {}
        cur["trials_expired_unconverted"] = int(cur.get("trials_expired_unconverted", 0)) + 1
        if was_active:
            cur["active_trials"] = max(0, int(cur.get("active_trials", 0)) - 1)
        cur["last_updated"] = now
        return cur

    store.store.transaction(PATH_SUMMARY, update_summary)
    log.info("Recorded trial expired without conversion for %s", sid)
    return record, True


def get_recent_trials(limit: int = 50) -> list[dict]:
    """List recent trials sorted by trial start time descending."""
    raw = store.store.get(PREFIX_TRIALS) or {}
    items = []
    if isinstance(raw, dict):
        for val in raw.values():
            if isinstance(val, dict) and "subscription_id" in val:
                items.append(val)
    items.sort(key=lambda x: x.get("trial_started_at", x.get("created_at", 0)), reverse=True)
    return items[:limit]


def get_full_report(limit: int = 50) -> dict:
    """Return both aggregated conversion metrics and recent trial list."""
    summary = get_summary()
    recent = get_recent_trials(limit=limit)
    return {
        "summary": summary,
        "recent_trials": recent,
    }
