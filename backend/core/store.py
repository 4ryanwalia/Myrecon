"""
Persistent state for accounts: plan, weekly usage, payments, guest counters.

The API was stateless until accounts existed, and Render's free tier has no
disk that survives a deploy. The Firebase project the app already uses has a
Realtime Database, so account state lives there under `/web`, written only by
this server with a service account. The database rules deny `/web` to every
client (the root is `.read/.write: false` and nothing below grants it), so a
signed-in browser cannot edit its own plan.

Every read-modify-write goes through `transaction()`, which uses the REST
API's ETag / if-match support. Two gunicorn workers consuming the same user's
last scan at once cannot both succeed: the second write gets 412 and retries
against the new value.

Without FIREBASE_SERVICE_ACCOUNT the store falls back to process memory. That
is right for local development and tests, and in production it is what keeps
the guest limit working while accounts are switched off (per worker, and
reset by a restart, which errs toward the visitor).
"""

import json
import base64
import threading
import time
from typing import Any, Callable, Optional, Tuple

import jwt
import requests

import config


class Abort(Exception):
    """Raised inside a transaction function to leave the value untouched."""


class _MemoryStore:
    backend = "memory"

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.RLock()
        self._seq = 0

    def get(self, path: str) -> Any:
        with self._lock:
            if path in self._data:
                return json.loads(json.dumps(self._data[path]))
            # A parent path returns its direct children, as RTDB does.
            prefix = path.rstrip("/") + "/"
            children = {
                k[len(prefix):]: v for k, v in self._data.items()
                if k.startswith(prefix) and "/" not in k[len(prefix):]
            }
            return json.loads(json.dumps(children)) if children else None

    def push(self, path: str, value: Any) -> str:
        """Store under a new chronologically sortable child id."""
        with self._lock:
            self._seq += 1
            key = f"{int(time.time() * 1000):013d}{self._seq:06d}"
            self._data[f"{path.rstrip('/')}/{key}"] = json.loads(json.dumps(value))
            return key

    def set(self, path: str, value: Any) -> None:
        with self._lock:
            self._data[path] = json.loads(json.dumps(value))

    def transaction(self, path: str, fn: Callable[[Any], Any]) -> Any:
        with self._lock:
            current = json.loads(json.dumps(self._data.get(path)))
            new = fn(current)
            if new is None:
                self._data.pop(path, None)
            else:
                self._data[path] = json.loads(json.dumps(new))
            return new

    def delete(self, path: str) -> None:
        with self._lock:
            for key in [k for k in self._data if k == path or k.startswith(path + "/")]:
                self._data.pop(key, None)


class _RTDBStore:
    backend = "rtdb"
    _SCOPES = (
        "https://www.googleapis.com/auth/firebase.database "
        "https://www.googleapis.com/auth/userinfo.email"
    )

    def __init__(self, db_url: str, service_account: dict):
        self._db = db_url.rstrip("/")
        self._sa = service_account
        self._token: Optional[str] = None
        self._token_exp = 0.0
        self._lock = threading.Lock()
        self._http = requests.Session()

    def _access_token(self) -> str:
        """OAuth2 token for the service account, via a signed JWT assertion."""
        with self._lock:
            if self._token and time.time() < self._token_exp - 300:
                return self._token
            now = int(time.time())
            assertion = jwt.encode(
                {
                    "iss": self._sa["client_email"],
                    "scope": self._SCOPES,
                    "aud": "https://oauth2.googleapis.com/token",
                    "iat": now,
                    "exp": now + 3600,
                },
                self._sa["private_key"],
                algorithm="RS256",
                headers={"kid": self._sa.get("private_key_id", "")},
            )
            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                timeout=10,
            )
            resp.raise_for_status()
            body = resp.json()
            self._token = body["access_token"]
            self._token_exp = time.time() + int(body.get("expires_in", 3600))
            return self._token

    def _url(self, path: str) -> str:
        return f"{self._db}/{path.strip('/')}.json"

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {"Authorization": f"Bearer {self._access_token()}"}
        h.update(extra or {})
        return h

    def _get_with_etag(self, path: str) -> Tuple[Any, str]:
        resp = self._http.get(self._url(path), timeout=10,
                              headers=self._headers({"X-Firebase-ETag": "true"}))
        resp.raise_for_status()
        return resp.json(), resp.headers.get("ETag", "")

    def get(self, path: str) -> Any:
        resp = self._http.get(self._url(path), timeout=10, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def push(self, path: str, value: Any) -> str:
        """POST creates a child with a server-generated, chronological id."""
        resp = self._http.post(self._url(path), data=json.dumps(value),
                               timeout=10, headers=self._headers())
        resp.raise_for_status()
        return resp.json()["name"]

    def set(self, path: str, value: Any) -> None:
        resp = self._http.put(self._url(path), data=json.dumps(value),
                              timeout=10, headers=self._headers())
        resp.raise_for_status()

    def transaction(self, path: str, fn: Callable[[Any], Any], retries: int = 10) -> Any:
        for _ in range(retries):
            current, etag = self._get_with_etag(path)
            new = fn(current)
            headers = self._headers({"if-match": etag})
            if new is None:
                resp = self._http.delete(self._url(path), timeout=10, headers=headers)
            else:
                resp = self._http.put(self._url(path), data=json.dumps(new),
                                      timeout=10, headers=headers)
            if resp.status_code == 412:
                continue  # someone else wrote first; recompute on the new value
            resp.raise_for_status()
            return new
        raise RuntimeError("store transaction kept conflicting")

    def delete(self, path: str) -> None:
        self._http.delete(self._url(path), timeout=10, headers=self._headers()).raise_for_status()


def _load_service_account(raw: str) -> Optional[dict]:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith("{"):
        raw = base64.b64decode(raw).decode()
    return json.loads(raw)


def _build():
    sa = _load_service_account(config.FIREBASE_SERVICE_ACCOUNT)
    if sa and config.FIREBASE_DB_URL:
        return _RTDBStore(config.FIREBASE_DB_URL, sa)
    return _MemoryStore()


store = _build()


def persistent() -> bool:
    """True when state survives restarts, i.e. accounts can be offered.

    The local test account (config.DEV_TEST_ACCOUNT, never on in production)
    is allowed to use memory, which is all a test purchase needs.
    """
    return store.backend == "rtdb" or config.DEV_TEST_ACCOUNT
