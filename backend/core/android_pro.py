"""Anonymous Android subscription verification. No purchase tokens/results persisted.

Runs on the existing backend, not Spark Cloud Functions. Firebase is an owner-only
metadata projection. Access always requires a fresh Google API verification.
"""
import hashlib
import time
from datetime import datetime
from urllib.parse import quote

import requests
import jwt
import config
from core import android_referrals as integrity, store as storage
from core.firebase_auth import verify_id_token, AuthError

PRODUCTS = {"myrecon_pro_monthly", "myrecon_pro_yearly"}
ACTIVE = {"SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD", "SUBSCRIPTION_STATE_CANCELED"}


class RestoreRequired(ValueError):
    pass


def account_id(uid):
    return hashlib.sha256(("myrecon-play:" + uid).encode()).hexdigest()


def timestamp(value):
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, TypeError, AttributeError):
        return 0


def entitlement(remote, uid, now_ms=None, allow_restore=False):
    """Only extract metadata; never store the raw Play response (may contain PII)."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if not allow_restore and remote.get("externalAccountIdentifiers", {}).get("obfuscatedExternalAccountId") != account_id(uid):
        raise RestoreRequired("A fresh Play Integrity proof is required to restore this purchase.")
    items = [x for x in remote.get("lineItems", []) if x.get("productId") in PRODUCTS]
    item = max(items, key=lambda x: timestamp(x.get("expiryTime")), default={})
    expires = timestamp(item.get("expiryTime"))
    pro = remote.get("subscriptionState") in ACTIVE and expires > now_ms
    # Current offerPhase is authoritative. offerId alone remains after the trial.
    trial = pro and "freeTrial" in item.get("offerPhase", {})
    return {"isPro": pro, "productId": item.get("productId", ""), "expiresAtMs": expires,
            "verifiedUntilMs": min(expires, now_ms + 15 * 60_000) if pro else 0,
            "trialEndsAtMs": expires if trial else 0,
            "autoRenewEnabled": item.get("autoRenewingPlan", {}).get("autoRenewEnabled", False)}


def verify_purchase(uid, token, allow_restore=False):
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise ValueError("Invalid purchase token.")
    # Separate scope/cache from Play Integrity. Credentials are already held only by the server.
    from core import android_publisher
    headers = {"Authorization": "Bearer " + android_publisher.access_token()}
    base = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{integrity.PACKAGE}"
    reply = requests.get(base + "/purchases/subscriptionsv2/tokens/" + quote(token, safe=""), headers=headers, timeout=15)
    if reply.status_code in (400, 404, 410):
        return {"isPro": False, "productId": "", "expiresAtMs": 0, "verifiedUntilMs": 0, "trialEndsAtMs": 0, "autoRenewEnabled": False}
    reply.raise_for_status()
    remote = reply.json()
    result = entitlement(remote, uid, allow_restore=allow_restore)
    if result["isPro"] and remote.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_PENDING":
        ack = requests.post(base + "/purchases/subscriptions/" + quote(result["productId"], safe="") + "/tokens/" + quote(token, safe="") + ":acknowledge", headers=headers, json={}, timeout=15)
        ack.raise_for_status()
    # Only write when these three metadata fields change. Never persist token/PII.
    public = {k: result[k] for k in ("isPro", "productId", "expiresAtMs")}
    path = "android_installs/" + uid + "/subscription"
    if storage.store.get(path) != public:
        storage.store.set(path, public)
    return result


def register_routes(app, json_body, responses):
    from flask import request

    def identity():
        bearer = request.headers.get("Authorization", "")
        if not bearer.startswith("Bearer "):
            raise AuthError("Anonymous sign-in required.")
        claims = verify_id_token(bearer[7:])
        if claims.get("firebase", {}).get("sign_in_provider") != "anonymous":
            raise AuthError("Anonymous installation identity required.")
        return claims["sub"]

    @app.route("/api/android/pro/challenge", methods=["POST"])
    def android_restore_challenge():
        try:
            uid = identity()
            if not integrity.configured():
                return responses.error("Play restoration is not configured.", status=503)
            token = json_body().get("purchaseToken")
            if not isinstance(token, str) or not 1 <= len(token) <= 4096:
                raise ValueError()
            now = int(time.time())
            challenge = jwt.encode({"purpose": "play-restore", "uid": uid,
                "purchaseHash": hashlib.sha256(token.encode()).hexdigest(), "iat": now, "exp": now + 180}, config.SECRET_KEY, algorithm="HS256")
            return responses.ok({"challenge": challenge, "project_number": integrity.PROJECT_NUMBER})
        except AuthError:
            return responses.error("Anonymous sign-in required.", status=401)
        except ValueError:
            return responses.error("Invalid purchase token.", status=400)

    @app.route("/api/android/pro/verify", methods=["POST"])
    def android_pro_verify():
        try:
            uid = identity()
            if storage.store.backend != "rtdb":
                return responses.error("Durable billing storage unavailable.", status=503)
            body = json_body()
            purchase = body.get("purchaseToken")
            restore = False
            if body.get("challenge"):
                signed, proof = body.get("challenge"), body.get("integrity_token")
                if not isinstance(signed, str) or len(signed) > 4096 or not isinstance(proof, str) or len(proof) > 20000 or not isinstance(purchase, str):
                    raise ValueError("Invalid restore proof.")
                claim = jwt.decode(signed, config.SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "iat", "uid", "purpose", "purchaseHash"]})
                if claim["purpose"] != "play-restore" or claim["uid"] != uid or claim["purchaseHash"] != hashlib.sha256(purchase.encode()).hexdigest():
                    raise ValueError("Invalid restore proof.")
                integrity._verify_integrity(integrity._decode_integrity(proof), integrity.request_hash(signed))
                restore = True
            return responses.ok(verify_purchase(uid, purchase, allow_restore=restore))
        except AuthError:
            return responses.error("Anonymous sign-in required.", status=401)
        except RestoreRequired:
            return responses.error("Play Integrity required for restore.", status=409, code="play_restore_required")
        except (jwt.PyJWTError, integrity.Rejected):
            return responses.error("Invalid restore proof.", status=403)
        except ValueError as exc:
            return responses.error(str(exc), status=403)
        except (requests.RequestException, RuntimeError, KeyError):
            return responses.error("Google Play verification temporarily unavailable.", status=503)
