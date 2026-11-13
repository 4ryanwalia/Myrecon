"""Short-lived service-account OAuth credential; never expose it to Android."""
import threading
import time
import jwt
import requests
import config
from core.store import _load_service_account

_lock = threading.Lock()
_token = ""
_expires = 0


def access_token():
    global _token, _expires
    with _lock:
        if _token and time.time() < _expires - 60:
            return _token
        sa = _load_service_account(config.FIREBASE_SERVICE_ACCOUNT)
        now = int(time.time())
        assertion = jwt.encode({"iss": sa["client_email"], "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600}, sa["private_key"], algorithm="RS256")
        response = requests.post("https://oauth2.googleapis.com/token", data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}, timeout=10)
        response.raise_for_status()
        data = response.json()
        _token, _expires = data["access_token"], now + int(data.get("expires_in", 3600))
        return _token
