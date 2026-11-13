"""Private anonymous referral ledger. All credit changes use per-install transactions.

Only anonymous IDs, counters, and replay receipts persist. Query data stays in
the short-lived signed challenge and process memory, never in Firebase.
"""
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, unquote
import jwt
import requests
import config
from core import android_referrals as proof, store as storage, validation
from core.firebase_auth import AuthError, verify_id_token


def _path(uid):
    return "android_installs/" + uid + "/referral"


def _empty(code=""):
    return {"code": code, "referredBy": "", "bonusDeepCredits": 0, "invitesCompleted": 0,
            "awards": {}, "debits": {}}


def _public(record):
    return {k: record.get(k, default) for k, default in (
        ("code", ""), ("referredBy", ""), ("bonusDeepCredits", 0), ("invitesCompleted", 0))}


def _project(uid, record):
    # The API returns only these four fields. Rules hide anonymous replay receipts.
    return _public(record)


def initialize(uid, code):
    if not isinstance(code, str) or not proof._UUID.fullmatch(code):
        raise proof.Rejected()
    def bind(current):
        if current and current != uid:
            raise proof.Rejected()
        return uid
    existing_owner = storage.store.get("android_codes/" + code)
    if existing_owner != uid:
        storage.store.transaction("android_codes/" + code, bind)
    def init(current):
        current = current or _empty(code)
        if current["code"] != code:
            raise proof.Rejected()
        return current
    existing = storage.store.get(_path(uid))
    if existing and existing.get("code") == code:
        return _project(uid, existing)
    return _project(uid, storage.store.transaction(_path(uid), init))


def challenge(uid, body):
    ref = body.get("referrer")
    raw = body.get("installReferrer", "")
    if not isinstance(ref, str) or not proof._UUID.fullmatch(ref) or not isinstance(raw, str) or len(raw) > 2048:
        raise proof.Rejected()
    # Bind exactly the referrer retrieved from Play, rather than a manually entered code.
    parsed = parse_qs(unquote(raw))
    if parsed.get("ref", [None])[0] != ref:
        raise proof.Rejected()
    try:
        click, install = int(body.get("clickSeconds", 0)), int(body.get("installSeconds", 0))
    except (TypeError, ValueError):
        raise proof.Rejected()
    now = int(time.time())
    if not 0 < click <= install <= now + 300 or install - click > 90 * 86400:
        raise proof.Rejected()
    owner = storage.store.get("android_codes/" + ref)
    own = storage.store.get(_path(uid))
    if not owner:
        raise proof.Unavailable()
    if owner == uid or not own or own.get("referredBy") not in ("", ref):
        raise proof.Rejected()
    username = validation.username(body.get("username", ""))
    # No query/handle goes into any persisted record, log, analytics, or WorkData.
    return {"challenge": jwt.encode({"purpose": "growth-referral", "uid": uid, "referrerUid": owner,
        "referrer": ref, "username": username, "iat": now, "exp": now + 180,
        "jti": secrets.token_hex(16)}, config.SECRET_KEY, algorithm="HS256"), "project_number": proof.PROJECT_NUMBER}


def _award(uid, receipt, invited=False, referred_by=None):
    def update(record):
        if not record:
            raise proof.Rejected()
        if referred_by and record.get("referredBy") not in ("", referred_by):
            raise proof.Rejected()
        awards = record.setdefault("awards", {})
        if receipt not in awards:
            record["bonusDeepCredits"] = min(10, int(record.get("bonusDeepCredits", 0)) + 2)
            record["invitesCompleted"] = int(record.get("invitesCompleted", 0)) + int(invited)
            awards[receipt] = True
        if referred_by:
            record["referredBy"] = referred_by
        return record
    record = storage.store.transaction(_path(uid), update)
    _project(uid, record)
    return record


def redeem(uid, body):
    token, integrity = body.get("challenge"), body.get("integrity_token")
    if not isinstance(token, str) or len(token) > 4096 or not isinstance(integrity, str) or len(integrity) > 20000:
        raise proof.Rejected()
    try:
        claim = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "iat", "uid", "purpose", "referrerUid", "referrer", "username"]})
    except jwt.PyJWTError:
        raise proof.Rejected()
    if claim["uid"] != uid or claim["purpose"] != "growth-referral":
        raise proof.Rejected()
    proof._verify_integrity(proof._decode_integrity(integrity), proof.request_hash(token))
    # _award atomically fixes first attribution; a proven retry can skip the scan.
    existing = storage.store.get(_path(uid))
    if not existing or existing.get("referredBy") not in ("", claim["referrer"]):
        raise proof.Rejected()
    if not existing.get("referredBy"):
        if not proof._scan_slot.acquire(blocking=False):
            raise proof.Unavailable()
        try:
            proof._qualifying_scan(claim["username"])
        finally:
            proof._scan_slot.release()
    # Recipient first: its immutable referredBy field binds retries to one referrer.
    receipt = hashlib.sha256(("referee:" + uid).encode()).hexdigest()
    _award(uid, "welcome", referred_by=claim["referrer"])
    _award(claim["referrerUid"], receipt, invited=True)
    return {"claim": "counted", **_public(storage.store.get(_path(uid)))}


def consume(uid, operation):
    if not isinstance(operation, str) or not proof._UUID.fullmatch(operation):
        raise proof.Rejected()
    outcome = {"consumed": False}
    def debit(record):
        outcome["consumed"] = False
        if not record:
            raise proof.Rejected()
        receipts = record.setdefault("debits", {})
        if operation in receipts:
            outcome["consumed"] = True
            return record
        if record.get("bonusDeepCredits", 0) > 0:
            record["bonusDeepCredits"] -= 1
            receipts[operation] = int(time.time() * 1000)
            # Old retries can spend another credit, but can never create one.
            record["debits"] = dict(sorted(receipts.items(), key=lambda pair: pair[1])[-32:])
            outcome["consumed"] = True
        return record
    record = storage.store.transaction(_path(uid), debit)
    return {**outcome, **_project(uid, record)}


def sync_counts(uid, body):
    # Cumulative absolute totals make network retries idempotent; never send deltas.
    incoming = body.get("counts", {})
    if not isinstance(incoming, dict) or set(incoming) != {"qr", "url", "extended", "deep"}:
        raise proof.Rejected()
    if any(type(v) is not int or not 0 <= v <= 2_000_000_000 for v in incoming.values()):
        raise proof.Rejected()
    def merge(current):
        return {key: max(int((current or {}).get(key, 0)), value) for key, value in incoming.items()}
    return {"counts": storage.store.transaction("android_installs/" + uid + "/counts", merge)}


def register_routes(app, json_body, responses):
    from flask import request
    @app.route("/api/android/growth/<action>", methods=["POST"])
    def android_growth(action):
        try:
            if not proof.configured():
                raise proof.Unavailable()
            bearer = request.headers.get("Authorization", "")
            if not bearer.startswith("Bearer "):
                raise AuthError("Anonymous sign-in required")
            claims = verify_id_token(bearer[7:])
            if claims.get("firebase", {}).get("sign_in_provider") != "anonymous":
                raise AuthError("Anonymous installation required")
            uid, body = claims["sub"], json_body()
            if action == "initialize": result = initialize(uid, body.get("code"))
            elif action == "status": result = _public(storage.store.get(_path(uid)) or _empty())
            elif action == "challenge": result = challenge(uid, body)
            elif action == "redeem": result = redeem(uid, body)
            elif action == "consume": result = consume(uid, body.get("operation"))
            elif action == "counts": result = sync_counts(uid, body)
            else: return responses.error("Unknown action", status=404)
            return responses.ok(result)
        except AuthError:
            return responses.error("Anonymous sign-in required", status=401)
        except (proof.Rejected, validation.ValidationError):
            return responses.error("Referral verification failed", status=403)
        except (proof.Unavailable, requests.RequestException, RuntimeError):
            return responses.error("Referral service unavailable; retry shortly", status=503)
