"""Website scan access and paid credits.

Guests retain their daily free allowance and first-100-platform preview.
Free accounts get five standard/full username scans per UTC day, shared
with quick scans. Accounts that bought the INR 99 pack get unlimited
standard scans, even after all ten Extended credits have been used.
The only new purchase is an Extended Scan Pack: INR 99 for ten 3,000+
platform scans, with no expiry or renewal. Packs add credits at
/web/users/<uid>/extended/scans_left. Existing weekly/monthly passes keep
their remaining Extended scans and original expiry in the legacy pro record.

Extended credits are spent transactionally when an uncached scan starts,
and restored to the same allowance if its pipeline fails. A cached result
requires a credit to be available but does not spend it. Paid order markers
and credits are written in one transaction so verification and webhooks can
arrive in either order without double grants. Only new order creation uses
PLANS; settlement also accepts LEGACY_PLANS for previously created orders.
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
from modules.sweep import EXTENDED_TOTAL as EXTENDED_PLATFORMS  # noqa: E402
GUEST_SCANS_PER_DAY = config.GUEST_SCANS_PER_DAY
FREE_STANDARD_SCANS_PER_DAY = 5
PLANS = {
    "extended": {"id": "extended", "label": "Extended Scan Pack", "price_inr": 99,
                 "days": None, "full_scans": None, "extended_scans": 10,
                 "standard_scans_unlimited": True},
}

# Previously sold passes remain valid, including orders paid during rollout.
# They cannot be purchased again through the order endpoint.
LEGACY_PLANS = {
    "weekly": {"id": "weekly", "label": "Pro Weekly", "price_inr": 99,
               "days": 7, "full_scans": 10, "extended_scans": 2},
    "monthly": {"id": "monthly", "label": "Pro Monthly", "price_inr": 299,
                "days": 30, "full_scans": 50, "extended_scans": 6},
}

_DAY_MS = 86_400_000


class NoAllowance(Exception):
    """Signed in, but no scans of this kind left. Carries the entitlements."""

    def __init__(self, ent: dict, scope: str = "full"):
        super().__init__(f"no {scope} scans left")
        self.entitlements = ent
        self.scope = scope


class GuestLimit(Exception):
    """A guest used today's scans."""


class StandardLimit(Exception):
    """A signed-in free account used its daily username allowance."""

    def __init__(self, ent: dict):
        super().__init__("standard daily limit reached")
        self.entitlements = ent


def _now_ms() -> int:
    return int(time.time() * 1000)




def _user_path(uid: str) -> str:
    return f"web/users/{uid}"


def _standard_day(now_ms: int) -> str:
    return _dt.datetime.fromtimestamp(now_ms / 1000, _dt.timezone.utc).strftime("%Y%m%d")


def _standard_reset(now_ms: int) -> int:
    now = _dt.datetime.fromtimestamp(now_ms / 1000, _dt.timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + _dt.timedelta(days=1)
    return int(tomorrow.timestamp() * 1000)


def entitlements(record, now_ms=None) -> dict:
    """What this account can do right now. Pure: no I/O."""
    now = now_ms if now_ms is not None else _now_ms()
    record = record or {}
    pro = record.get("pro") or {}
    pro_active = bool(pro) and pro.get("until", 0) > now
    pro_left = max(0, int(pro.get("scans_left", 0))) if pro_active else 0
    legacy_left = max(0, int(_extended_left(pro))) if pro_active else 0
    pack = record.get("extended") or {}
    pack_left = max(0, int(pack.get("scans_left", 0)))
    # Existing purchased packs already carry scans_left, including zero.
    # The paid standard benefit is not tied to remaining Extended credits.
    pack_purchased = "scans_left" in pack
    unlimited = pack_purchased or pro_active
    usage = record.get("standard_usage") or {}
    used = int(usage.get("used", 0)) if usage.get("day") == _standard_day(now) else 0
    free_left = max(0, FREE_STANDARD_SCANS_PER_DAY - used)
    return {
        "tier": "pro" if unlimited else "free",
        "plan": "extended" if pack_purchased else pro.get("plan") if pro_active else None,
        "pro_until": pro.get("until") if pro_active else None,
        "pro_scans_left": pro_left,
        # Null means unmetered, not an exhausted allowance.
        "free_scans_left": free_left,
        "free_scans_total": FREE_STANDARD_SCANS_PER_DAY,
        "full_scans_left": None if unlimited else free_left,
        "full_scans_unlimited": unlimited,
        "standard_scans_unlimited": unlimited,
        "standard_scans_left": None if unlimited else free_left,
        "standard_scans_per_day": None if unlimited else FREE_STANDARD_SCANS_PER_DAY,
        "standard_resets_at": None if unlimited else _standard_reset(now),
        "extended_scans_left": pack_left + legacy_left,
        "extended_pack_scans_left": pack_left,
        "extended_legacy_scans_left": legacy_left,
        "extended_legacy_until": pro.get("until") if legacy_left else None,
    }


def _extended_left(pro: dict) -> int:
    if "extended_left" in pro:
        return int(pro["extended_left"])
    return LEGACY_PLANS.get(pro.get("plan"), {}).get("extended_scans", 0)


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


def consume_standard_scan(uid: str):
    """Reserve a daily free scan atomically, or nothing for a paid account."""
    denied = {}
    spent = {}

    def fn(cur):
        cur = cur or {"created": _now_ms()}
        now = _now_ms()
        ent = entitlements(cur, now)
        if ent["standard_scans_unlimited"]:
            spent["source"] = None
            return cur
        if ent["standard_scans_left"] <= 0:
            denied["ent"] = ent
            raise Abort()
        day = _standard_day(now)
        cur["standard_usage"] = {"day": day, "used": FREE_STANDARD_SCANS_PER_DAY - ent["standard_scans_left"] + 1}
        spent["source"] = "standard:" + day
        return cur

    try:
        store.transaction(_user_path(uid), fn)
    except Abort:
        raise StandardLimit(denied["ent"])
    return spent["source"]


def consume_extended_scan(uid: str) -> str:
    """Spend expiring legacy scans first, then a non-expiring pack credit."""
    denied = {}
    spent = {}

    def fn(cur):
        cur = cur or {"created": _now_ms()}
        ent = entitlements(cur)
        if ent["extended_scans_left"] <= 0:
            denied["ent"] = ent
            raise Abort()
        if ent["extended_legacy_scans_left"] > 0:
            cur["pro"]["extended_left"] = ent["extended_legacy_scans_left"] - 1
            spent["source"] = "extended"
        else:
            cur["extended"]["scans_left"] = ent["extended_pack_scans_left"] - 1
            spent["source"] = "extended_pack"
        return cur

    try:
        store.transaction(_user_path(uid), fn)
    except Abort:
        raise NoAllowance(denied["ent"], "extended")
    return spent["source"]


def refund_full_scan(uid: str, source: str) -> None:
    """Give back a scan whose pipeline failed. Best effort."""
    if not uid or not source:
        return

    def fn(cur):
        if not cur:
            raise Abort()
        if source.startswith("standard:"):
            usage = cur.get("standard_usage") or {}
            if usage.get("day") == source.split(":", 1)[1]:
                usage["used"] = max(0, int(usage.get("used", 0)) - 1)
                cur["standard_usage"] = usage
        elif source == "extended_pack":
            pack = cur.setdefault("extended", {})
            pack["scans_left"] = int(pack.get("scans_left", 0)) + 1
        elif source == "extended" and cur.get("pro"):
            cur["pro"]["extended_left"] = _extended_left(cur["pro"]) + 1
        return cur

    try:
        store.transaction(_user_path(uid), fn)
    except Exception:  # noqa: BLE001 - never fail a response over a refund
        pass


def grant_pass(uid: str, plan_id: str, payment_ref: str) -> bool:
    """
    Apply a paid pass exactly once per payment reference (the Razorpay order
    id). Both the browser's verify call and Razorpay's webhook land here, in
    either order. The idempotency marker and entitlement update share one
    user-record transaction, so a failed database write cannot leave a payment
    marked as processed before its scans were granted. Returns True when the
    pass is active for this order, including a retry after a successful grant.
    """
    plan = (PLANS | LEGACY_PLANS)[plan_id]
    ref_key = hashlib.sha256(payment_ref.encode()).hexdigest()[:40]
    payment_path = f"web/payments/{ref_key}"
    if store.get(payment_path) is not None:
        return False

    applied = {"value": False}

    def apply(cur):
        cur = cur or {"created": _now_ms()}
        payments = cur.get("payments") or {}
        if ref_key in payments:
            # A previous attempt committed the pass but failed before it could
            # write the compatibility ledger. Repair the ledger on retry
            # without adding scans a second time.
            applied["value"] = True
            return cur

        now = _now_ms()
        if plan_id in PLANS:
            pack = cur.setdefault("extended", {})
            pack["scans_left"] = int(pack.get("scans_left", 0)) + plan["extended_scans"]
        else:
            pro = cur.get("pro") or {}
            active = pro.get("until", 0) > now
            start = pro["until"] if active else now
            cur["pro"] = {
                "plan": plan_id if not active else _longer(pro.get("plan"), plan_id),
                "until": start + plan["days"] * _DAY_MS,
                "scans_left": (int(pro.get("scans_left", 0)) if active else 0) + plan["full_scans"],
                "extended_left": (_extended_left(pro) if active else 0) + plan["extended_scans"],
            }
        # RTDB transacts this marker and the allowance together, so concurrent
        # webhook and UI verification calls cannot grant this order twice.
        payments[ref_key] = True
        cur["payments"] = payments
        applied["value"] = True
        return cur

    store.transaction(_user_path(uid), apply)

    # Keep the shared ledger for operational lookup and compatibility. If
    # this write fails, a retry is still safe because the user record has the
    # idempotency marker already.
    def record(cur):
        return cur or {"uid": uid, "plan": plan_id, "ref": payment_ref, "at": _now_ms()}

    store.transaction(payment_path, record)
    return applied["value"]


def _longer(a, b):
    return a if a and LEGACY_PLANS.get(a, {}).get("days", 0) >= LEGACY_PLANS[b]["days"] else b


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
