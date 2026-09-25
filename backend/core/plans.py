"""
Who may run which scan, and how many.

  guest       standard scan (100 platforms), GUEST_SCANS_PER_DAY per address
  free        standard scans unmetered, FREE_FULL_PER_WEEK full scans a week
  pro weekly  PLANS["weekly"]: a 7-day pass with its own full-scan allowance
  pro monthly PLANS["monthly"]: a 30-day pass, same idea

A "full" scan is the 560-platform sweep ported from the Android app. Every
other tool stays free for everyone; accounts only change scan limits.

Passes are one-time payments, not subscriptions: nothing renews, so nothing
has to be cancelled. Buying while a pass is active stacks, extending the end
date and adding the scans.

A full scan is charged when it starts and refunded if the pipeline fails, so
a crashed scan never costs anything. Pro allowance is spent before the free
weekly allowance, so free scans are still there once a pass runs out.

Record at /web/users/<uid>:
  {"email", "name", "created",
   "pro":  {"plan", "until" (ms), "scans_left"},
   "free": {"week": "2026-W39", "used"}}
"""

import datetime as _dt
import hashlib
import hmac
import threading
import time

import config
from core.store import Abort, store

from modules.username_checker import STANDARD_LIMIT as STANDARD_PLATFORMS  # noqa: E402
from modules.sweep import TOTAL as FULL_PLATFORMS  # noqa: E402
GUEST_SCANS_PER_DAY = config.GUEST_SCANS_PER_DAY
FREE_FULL_PER_WEEK = config.FREE_FULL_PER_WEEK

PLANS = {
    "weekly": {"id": "weekly", "label": "Pro Weekly", "price_inr": 99,
               "days": 7, "full_scans": 50},
    "monthly": {"id": "monthly", "label": "Pro Monthly", "price_inr": 299,
                "days": 30, "full_scans": 200},
}

_DAY_MS = 86_400_000


class NoAllowance(Exception):
    """Signed in, but no full scans left. Carries the entitlements."""

    def __init__(self, ent: dict):
        super().__init__("no full scans left")
        self.entitlements = ent


class GuestLimit(Exception):
    """A guest used today's scans."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _iso_week(ms: int) -> str:
    d = _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _next_monday_ms(ms: int) -> int:
    d = _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc)
    start = (d - _dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((start + _dt.timedelta(days=7)).timestamp() * 1000)


def _user_path(uid: str) -> str:
    return f"web/users/{uid}"


def entitlements(record, now_ms=None) -> dict:
    """What this account can do right now. Pure: no I/O."""
    now = now_ms if now_ms is not None else _now_ms()
    record = record or {}
    pro = record.get("pro") or {}
    pro_active = bool(pro) and pro.get("until", 0) > now
    free = record.get("free") or {}
    week = _iso_week(now)
    free_used = free.get("used", 0) if free.get("week") == week else 0
    free_left = max(0, FREE_FULL_PER_WEEK - free_used)
    pro_left = max(0, int(pro.get("scans_left", 0))) if pro_active else 0
    return {
        "tier": "pro" if pro_active else "free",
        "plan": pro.get("plan") if pro_active else None,
        "pro_until": pro.get("until") if pro_active else None,
        "pro_scans_left": pro_left,
        "free_scans_left": free_left,
        "free_scans_per_week": FREE_FULL_PER_WEEK,
        "free_resets_at": _next_monday_ms(now),
        "full_scans_left": pro_left + free_left,
    }


def get_account(uid: str, email: str = "", name: str = "") -> dict:
    """Read (creating on first sight) the account and its entitlements."""
    def touch(cur):
        cur = cur or {"created": _now_ms()}
        if email:
            cur["email"] = email[:254]
        if name:
            cur["name"] = name[:120]
        return cur

    record = store.get(_user_path(uid))
    if record is None or (email and record.get("email") != email):
        record = store.transaction(_user_path(uid), touch)
    return {"uid": uid, "email": record.get("email", ""), **entitlements(record)}


def consume_full_scan(uid: str) -> str:
    """Spend one full scan. Returns which allowance paid ("pro" / "free")."""
    spent = {}

    def fn(cur):
        cur = cur or {"created": _now_ms()}
        ent = entitlements(cur)
        if ent["pro_scans_left"] > 0:
            cur["pro"]["scans_left"] = ent["pro_scans_left"] - 1
            spent["source"] = "pro"
        elif ent["free_scans_left"] > 0:
            week = _iso_week(_now_ms())
            free = cur.get("free") or {}
            used = free.get("used", 0) if free.get("week") == week else 0
            cur["free"] = {"week": week, "used": used + 1}
            spent["source"] = "free"
        else:
            spent["denied"] = ent
            raise Abort()
        return cur

    try:
        store.transaction(_user_path(uid), fn)
    except Abort:
        raise NoAllowance(spent["denied"])
    return spent["source"]


def refund_full_scan(uid: str, source: str) -> None:
    """Give back a scan whose pipeline failed. Best effort."""
    def fn(cur):
        if not cur:
            raise Abort()
        if source == "pro" and cur.get("pro"):
            cur["pro"]["scans_left"] = int(cur["pro"].get("scans_left", 0)) + 1
        elif source == "free" and cur.get("free"):
            cur["free"]["used"] = max(0, int(cur["free"].get("used", 0)) - 1)
        return cur

    try:
        store.transaction(_user_path(uid), fn)
    except Exception:  # noqa: BLE001 - never fail a response over a refund
        pass


def grant_pass(uid: str, plan_id: str, payment_ref: str) -> bool:
    """
    Apply a paid pass exactly once per payment reference (the Razorpay order
    id). Both the browser's verify call and Razorpay's webhook land here, in
    either order, and only the first one counts. Returns True if it applied.
    """
    plan = PLANS[plan_id]
    ref_key = hashlib.sha256(payment_ref.encode()).hexdigest()[:40]
    claimed = {}

    def claim(cur):
        if cur is not None:
            raise Abort()
        claimed["ok"] = True
        return {"uid": uid, "plan": plan_id, "ref": payment_ref, "at": _now_ms()}

    try:
        store.transaction(f"web/payments/{ref_key}", claim)
    except Abort:
        return False

    def apply(cur):
        cur = cur or {"created": _now_ms()}
        now = _now_ms()
        pro = cur.get("pro") or {}
        active = pro.get("until", 0) > now
        start = pro["until"] if active else now
        cur["pro"] = {
            "plan": plan_id if not active else _longer(pro.get("plan"), plan_id),
            "until": start + plan["days"] * _DAY_MS,
            "scans_left": (int(pro.get("scans_left", 0)) if active else 0) + plan["full_scans"],
        }
        return cur

    store.transaction(_user_path(uid), apply)
    return True


def _longer(a, b):
    return a if a and PLANS.get(a, {}).get("days", 0) >= PLANS[b]["days"] else b


# ── Guests ───────────────────────────────────────────────────────

_sweep_lock = threading.Lock()
_swept_day = {"day": ""}


def _guest_key(ip: str, day: str) -> str:
    # Keyed and rotated daily: the stored value cannot be turned back into an
    # address without the server's secret, and yesterday's key is useless.
    return hmac.new(config.SECRET_KEY.encode(), f"{day}|{ip}".encode(),
                    hashlib.sha256).hexdigest()[:32]


def consume_guest_scan(ip: str) -> int:
    """Count a guest scan. Returns scans left today; raises GuestLimit."""
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    _forget_old_days(day)
    left = {}

    def fn(cur):
        used = int(cur or 0)
        if used >= GUEST_SCANS_PER_DAY:
            raise Abort()
        left["n"] = GUEST_SCANS_PER_DAY - used - 1
        return used + 1

    try:
        store.transaction(f"web/guest/{day}/{_guest_key(ip, day)}", fn)
    except Abort:
        raise GuestLimit()
    return left["n"]


def _forget_old_days(today: str) -> None:
    """Drop the day before yesterday's counters, once per process per day."""
    with _sweep_lock:
        if _swept_day["day"] == today:
            return
        _swept_day["day"] = today
    for back in range(2, 9):  # a week, in case the server slept through some
        old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=back)).strftime("%Y%m%d")
        try:
            store.delete(f"web/guest/{old}")
        except Exception:  # noqa: BLE001 - housekeeping only
            pass
