"""
Firebase Authentication, verified server side without the Admin SDK.

The website signs people in with Google through Firebase Auth (the same
`myrecon-bugsnaps` project the Android app uses). The browser sends the
Firebase ID token as `Authorization: Bearer <token>`; this module checks it the
way Firebase documents for third-party JWT libraries:

  * RS256, signed by a key in Google's published securetoken certificates
  * aud == project id, iss == https://securetoken.google.com/<project id>
  * exp in the future, iat and auth_time in the past, sub non-empty

firebase-admin would do the same and pull in grpc and the Firestore client,
which a 512 MB Render instance does not need. PyJWT is the whole dependency.

A bearer token, not a cookie: there is still no session or cookie for a
cross-site request to ride, so the CSRF reasoning in app.py is unchanged.
"""

import threading
import time

import jwt
import requests
from cryptography.x509 import load_pem_x509_certificate

import config

_CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
_lock = threading.Lock()
_keys: dict = {}
_keys_expire_at = 0.0


class AuthError(Exception):
    """The token was present but is not acceptable. Message is safe to show."""


def _public_keys(force: bool = False) -> dict:
    """kid -> public key, cached for as long as Google's Cache-Control allows."""
    global _keys, _keys_expire_at
    with _lock:
        if not force and _keys and time.time() < _keys_expire_at:
            return _keys
        resp = requests.get(_CERTS_URL, timeout=8)
        resp.raise_for_status()
        max_age = 3600
        for part in resp.headers.get("Cache-Control", "").split(","):
            part = part.strip()
            if part.startswith("max-age="):
                try:
                    max_age = int(part.split("=", 1)[1])
                except ValueError:
                    pass
        _keys = {
            kid: load_pem_x509_certificate(pem.encode()).public_key()
            for kid, pem in resp.json().items()
        }
        _keys_expire_at = time.time() + max_age
        return _keys


def verify_id_token(token: str) -> dict:
    """Return the verified claims, or raise AuthError."""
    project = config.FIREBASE_PROJECT_ID
    if not project:
        raise AuthError("Sign-in is not configured on this server.")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise AuthError("Malformed sign-in token.")
    if header.get("alg") != "RS256":
        raise AuthError("Unexpected sign-in token algorithm.")

    kid = header.get("kid", "")
    keys = _public_keys()
    if kid not in keys:
        # Google rotates keys; a kid we have not seen may simply be newer
        # than our cache.
        keys = _public_keys(force=True)
    key = keys.get(kid)
    if key is None:
        raise AuthError("Sign-in token was signed by an unknown key.")

    try:
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=project,
            issuer=f"https://securetoken.google.com/{project}",
            leeway=30,
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Your sign-in has expired. Please sign in again.")
    except jwt.PyJWTError:
        raise AuthError("Sign-in token could not be verified.")

    now = time.time() + 30
    if not claims.get("sub") or len(claims["sub"]) > 128:
        raise AuthError("Sign-in token has no user.")
    if claims.get("iat", now) > now or claims.get("auth_time", 0) > now:
        raise AuthError("Sign-in token is not valid yet.")
    return claims
