"""Server-owned Android referral grants. Client database writes are never trusted."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time

import jwt
import requests

import config
from core import store as storage, validation

PACKAGE = "com.Myrecon.osint"
PROJECT_NUMBER = 549280929178
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_scan_slot = threading.BoundedSemaphore(1)
_oauth_lock = threading.Lock()
_oauth_token = ""
_oauth_expires = 0


class Unavailable(Exception):
    pass


class Rejected(Exception):
    pass


def _certificates():
    result = set()
    for raw in os.environ.get("ANDROID_REFERRAL_CERT_SHA256", "").split(","):
        value = raw.strip().replace(":", "").lower()
        if _HASH.fullmatch(value):
            result.add(base64.urlsafe_b64encode(bytes.fromhex(value)).decode().rstrip("="))
    return result


def configured():
    return storage.store.backend == "rtdb" and bool(config.SECRET_KEY and
        config.FIREBASE_SERVICE_ACCOUNT and _certificates())


def request_hash(challenge):
    return base64.urlsafe_b64encode(hashlib.sha256(challenge.encode()).digest()).decode().rstrip("=")


def challenge(body):
    if not configured():
        raise Unavailable()
    if not isinstance(body, dict):
        raise Rejected()
    own, referrer, claim = (body.get(k) for k in ("own_code", "referrer", "claim_key"))
    if not all(isinstance(v, str) for v in (own, referrer, claim)):
        raise Rejected()
    if not _UUID.fullmatch(own) or not _UUID.fullmatch(referrer) or not _HASH.fullmatch(claim) or own == referrer:
        raise Rejected()
    username = validation.username(body.get("username", ""))
    now = int(time.time())
    token = jwt.encode({"purpose": "android-referral", "own_code": own, "referrer": referrer,
        "claim_key": claim, "username": username, "iat": now, "exp": now + 180,
        "jti": secrets.token_hex(16)}, config.SECRET_KEY, algorithm="HS256")
    return {"challenge": token, "project_number": PROJECT_NUMBER}


def _access_token():
    global _oauth_token, _oauth_expires
    with _oauth_lock:
        if _oauth_token and time.time() < _oauth_expires - 60:
            return _oauth_token
        sa = storage._load_service_account(config.FIREBASE_SERVICE_ACCOUNT)
        now = int(time.time())
        assertion = jwt.encode({"iss": sa["client_email"],
            "scope": "https://www.googleapis.com/auth/playintegrity",
            "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600},
            sa["private_key"], algorithm="RS256", headers={"kid": sa.get("private_key_id", "")})
        reply = requests.post("https://oauth2.googleapis.com/token", data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}, timeout=10)
        reply.raise_for_status()
        body = reply.json()
        _oauth_token = body["access_token"]
        _oauth_expires = time.time() + int(body.get("expires_in", 3600))
        return _oauth_token


def _decode_integrity(token):
    reply = requests.post(f"https://playintegrity.googleapis.com/v1/{PACKAGE}:decodeIntegrityToken",
        headers={"Authorization": f"Bearer {_access_token()}"},
        json={"integrity_token": token}, timeout=15)
    reply.raise_for_status()
    return reply.json().get("tokenPayloadExternal", {})


def _verify_integrity(payload, expected_hash):
    if not isinstance(payload, dict) or any(not isinstance(payload.get(k, {}), dict)
        for k in ("requestDetails", "appIntegrity", "accountDetails", "deviceIntegrity")):
        raise Rejected()
    details = payload.get("requestDetails", {})
    app = payload.get("appIntegrity", {})
    try:
        age = time.time() * 1000 - int(details.get("timestampMillis", 0))
        version = int(app.get("versionCode", 0))
    except (ValueError, TypeError):
        raise Rejected()
    certificates = app.get("certificateSha256Digest", [])
    devices = payload.get("deviceIntegrity", {}).get("deviceRecognitionVerdict", [])
    if not isinstance(certificates, list) or not all(isinstance(v, str) for v in certificates) or not isinstance(devices, list):
        raise Rejected()
    if (details.get("requestPackageName") != PACKAGE or
        not hmac.compare_digest(str(details.get("requestHash", "")), expected_hash) or
        not -30_000 <= age <= 120_000 or
        app.get("appRecognitionVerdict") != "PLAY_RECOGNIZED" or
        app.get("packageName") != PACKAGE or version < 5 or
        not _certificates().intersection(certificates) or
        payload.get("accountDetails", {}).get("appLicensingVerdict") != "LICENSED" or
        "MEETS_DEVICE_INTEGRITY" not in devices):
        raise Rejected()


def _qualifying_scan(username):
    from modules.username_checker import UsernameChecker, PLATFORMS
    checker = UsernameChecker(max_workers=8, delay=0)
    checker.scan(username, deep=False)
    # Completion means every scheduled platform produced a verdict, not that
    # any account was found or that unknown provider outcomes establish absence.
    if len(checker.all_results) != len(PLATFORMS[:50]):
        raise Unavailable()


def redeem(body):
    if not configured():
        raise Unavailable()
    if not isinstance(body, dict):
        raise Rejected()
    token, proof = body.get("challenge"), body.get("integrity_token")
    if not isinstance(token, str) or not isinstance(proof, str) or not 1 <= len(token) <= 4096 or not 1 <= len(proof) <= 20_000:
        raise Rejected()
    try:
        claim = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"],
            options={"require": ["exp", "iat", "jti", "purpose", "own_code", "referrer", "claim_key", "username"]})
        if claim["purpose"] != "android-referral":
            raise Rejected()
        _verify_integrity(_decode_integrity(proof), request_hash(token))
    except jwt.PyJWTError:
        raise Rejected()
    except requests.RequestException:
        raise Unavailable()
    # Attestation is verified even on retries: knowing a device hash must not
    # expose its record or let an unauthenticated caller consume its claim.
    previous = storage.store.get("android_referrals/claims/" + claim["claim_key"])
    if previous or storage.store.get("claims/" + claim["claim_key"]):
        return {"claim": "already_counted"}
    if not _scan_slot.acquire(blocking=False):
        raise Unavailable()
    try:
        _qualifying_scan(claim["username"])
    finally:
        _scan_slot.release()
    outcome = {"claim": "counted"}
    def grant(current):
        current = current or {}
        claims = current.setdefault("claims", {})
        if claim["claim_key"] in claims:
            outcome["claim"] = "already_counted"
            return current
        claims[claim["claim_key"]] = {"referrer": claim["referrer"], "at": int(time.time() * 1000)}
        current.setdefault("grants", {})[claim["referrer"]] = True
        return current
    storage.store.transaction("android_referrals", grant)
    return outcome


def register_routes(app, json_body, responses):
    from flask import request
    @app.route("/api/android/referral/<action>", methods=["POST", "OPTIONS"])
    def android_referral(action):
        if request.method == "OPTIONS":
            return ("", 204)
        if action not in ("challenge", "redeem"):
            return responses.error("Unknown referral action.", status=404)
        try:
            result = challenge(json_body()) if action == "challenge" else redeem(json_body())
            return responses.ok(result)
        except (Rejected, validation.ValidationError):
            return responses.error("Referral verification failed. Install the current app from Google Play and try again.",
                status=403, code="referral_verification_failed")
        except Unavailable:
            return responses.error("Referral verification is temporarily unavailable. Your invite is saved for retry.",
                status=503, code="referral_unavailable")
