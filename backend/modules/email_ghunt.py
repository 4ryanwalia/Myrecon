"""Opt-in GHunt library worker using an operator-managed local installation.

The stock email CLI also collects Calendar data, so it is intentionally not
invoked. Only the exact-email public PROFILE identity is projected; the separate
public Maps reader retrieves reviews and counts. No credentials, contact
containers or raw output are exported.
"""
import base64
import binascii
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit

MAX_BYTES = 2_000_000
TIMEOUT_SECONDS = 40
_WORKER_SLOT = threading.BoundedSemaphore(1)


def _dict(value):
    return value if isinstance(value, dict) else {}


def text(value, limit=2000):
    """Scalar projection kept local so the isolated worker needs only stdlib."""
    return str(value)[:limit] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def normalize_ghunt(payload, email):
    if not isinstance(payload, dict) or payload.get("query") != email:
        raise ValueError("Identity mismatch")
    target = _dict(payload.get("profile"))
    contributor_id = str(target.get("personId", ""))
    if "PROFILE" not in _dict(target.get("sourceIds")) or not re.fullmatch(r"\d{15,25}", contributor_id):
        raise ValueError("No public identity")
    returned_email = _dict(_dict(target.get("emails")).get("PROFILE")).get("value")
    if returned_email and str(returned_email).casefold() != email.casefold():
        raise ValueError("Identity mismatch")
    photo = _dict(_dict(target.get("profilePhotos")).get("PROFILE"))
    avatar = text(photo.get("url"), 3000) if photo.get("isDefault") is False else ""
    try:
        parsed = urlsplit(avatar)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".googleusercontent.com") or parsed.username or parsed.password:
            avatar = ""
    except ValueError:
        avatar = ""
    fields = {"ID": contributor_id}
    edited = text(_dict(_dict(target.get("sourceIds")).get("PROFILE")).get("lastUpdated"), 80)
    if edited:
        fields["Last profile edit"] = edited
    enterprise = _dict(_dict(target.get("extendedData")).get("gplusData")).get("isEntrepriseUser")
    if isinstance(enterprise, bool):
        fields["Enterprise user"] = "Yes" if enterprise else "No"
    apps = _dict(_dict(target.get("inAppReachability")).get("PROFILE")).get("apps")
    lists = {"Active Google apps": [text(a, 80) for a in apps[:30] if isinstance(a, str)]} if isinstance(apps, list) else {}
    stats = {k: v for k, v in _dict(payload.get("stats")).items()
             if k in ("Reviews", "Ratings", "Photos", "Answers") and isinstance(v, int) and not isinstance(v, bool) and v >= 0}
    return {"platform": "Google", "url": f"https://www.google.com/maps/contrib/{contributor_id}/reviews",
            "username": "", "display_name": text(_dict(_dict(target.get("names")).get("PROFILE")).get("fullname")),
            "avatar_url": avatar, "bio": "", "location": "", "fields": fields, "lists": lists, "stats": stats,
            "reviews": [], "positions": [], "education": [], "source": "GHunt", "basis": "provider_email",
            "profile_status": "ok", "evidence": "GHunt exact-email lookup returned a public Google PROFILE container. Profile edit dates are not last-seen activity."}


def enrich_ghunt_email(email):
    if os.getenv("EMAIL_GHUNT_ENABLED", "false").lower() != "true":
        return _enrich_ghunt_email(email)
    if not _WORKER_SLOT.acquire(blocking=False):
        return {"status": "rate_limited", "profiles": [], "registrations": [], "sources": [
            {"name": "Google public profile", "provider": "GHunt", "status": "rate_limited",
             "reason": "A Google lookup is already running; retry after it completes."}]}
    try:
        return _enrich_ghunt_email(email)
    finally:
        _WORKER_SLOT.release()


def _enrich_ghunt_email(email):
    source = {"name": "Google public profile", "provider": "GHunt", "status": "disabled"}
    result = {"status": "disabled", "profiles": [], "registrations": [], "sources": [source]}
    if os.getenv("EMAIL_GHUNT_ENABLED", "false").lower() != "true":
        source["reason"] = "GHunt adapter is disabled on this backend."
        return result
    runtime_python = Path(__file__).resolve().parents[1] / ".venv" / "ghunt" / "bin" / "python"
    executable = Path(os.getenv("GHUNT_PYTHON_EXECUTABLE", "") or str(runtime_python))
    session = Path(os.getenv("GHUNT_SESSION_FILE", ""))
    session_secret = os.getenv("GHUNT_SESSION_B64", "").strip()
    if not executable.is_absolute() or not executable.is_file() or not (session_secret or (session.is_absolute() and session.is_file())):
        result["status"] = source["status"] = "unconfigured"
        source["reason"] = "Install the isolated GHunt runtime and configure GHUNT_SESSION_B64 or an absolute GHUNT_SESSION_FILE after separate operator login."
        return result
    if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        result["status"] = source["status"] = "unknown"
        return result
    try:
        with tempfile.TemporaryDirectory(prefix="myrecon-ghunt-") as directory:
            output = Path(directory) / "public.json"
            # GHunt writes refreshed credentials even when the login is valid.
            # Copy mounted secrets as well as env secrets to a writable private
            # file; hosting secret mounts must never be modified by the worker.
            if not session_secret:
                with session.open("rb") as handle:
                    raw_session = handle.read(MAX_BYTES + 1)
                if len(raw_session) > MAX_BYTES:
                    raise ValueError("Session limit")
                session_secret = raw_session.decode("utf-8").strip()
            if len(session_secret) > MAX_BYTES:
                raise ValueError("Session limit")
            decoded = json.loads(base64.b64decode(session_secret, validate=True))
            if not isinstance(decoded, dict):
                raise ValueError("Session format")
            session = Path(directory) / "session.m"
            with session.open("x", encoding="utf-8") as handle:
                session.chmod(0o600)
                handle.write(session_secret)
            env = dict(os.environ)
            # No application/provider tokens are needed by the isolated worker.
            for name in list(env):
                if any(word in name.upper() for word in ("TOKEN", "API_KEY", "APIKEY", "PASSWORD", "SECRET")):
                    env.pop(name, None)
            env.pop("GHUNT_SESSION_B64", None)
            env.pop("FIREBASE_SERVICE_ACCOUNT", None)
            command = [str(executable), "-I", str(Path(__file__).resolve()), "--worker", str(output), str(session)]
            completed = subprocess.run(command, input=json.dumps({"email": email}), text=True,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=TIMEOUT_SECONDS, shell=False, cwd=directory, env=env)
            if completed.returncode != 0 or not output.is_file():
                raise ValueError("Worker failed")
            with output.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Output limit")
            payload = json.loads(raw)
            status = payload.get("status") if isinstance(payload, dict) else None
            if status not in ("found", "no_match", "authentication_required", "unavailable"):
                raise ValueError("Worker contract")
            source["status"] = status
            if status == "found":
                result["profiles"].append(normalize_ghunt(payload, email))
                source["reason"] = "Public Google identity retrieved for the exact email."
            elif status == "authentication_required":
                source["reason"] = "GHunt session must be authenticated separately by the operator."
            result["status"] = "ok" if status in ("found", "no_match") else status
    except subprocess.TimeoutExpired:
        result["status"] = source["status"] = "timeout"
    except (OSError, ValueError, TypeError, binascii.Error):
        result["status"] = source["status"] = "unavailable"
    return result


async def _public_worker(email, session):
    """No login dialog, Calendar, Play Games, geolocation inference or cookies extraction."""
    from importlib.metadata import version
    if version("ghunt") != "2.3.4":
        return {"status": "unavailable"}
    from ghunt import globals as gb
    from ghunt.objects.base import GHuntCreds
    from ghunt.objects.encoders import GHuntEncoder
    from ghunt.apis.peoplepa import PeoplePaHttp
    from ghunt.helpers import auth
    from ghunt.errors import GHuntInvalidSession, GHuntLoginError
    from ghunt.helpers.utils import get_httpx_client
    gb.init_globals()
    creds = GHuntCreds(session)
    try:
        creds.load_creds(silent=True)
    except GHuntInvalidSession:
        return {"status": "authentication_required"}
    async with get_httpx_client() as client:
        try:
            await auth.check_and_gen(client, creds)
        except (GHuntInvalidSession, GHuntLoginError):
            return {"status": "authentication_required"}
        # Only the exact-email public identity is needed here. GHunt's optional
        # cover-photo parser currently assumes metadata Google no longer sends.
        # The separate public Maps reader supplies names, photos and review counts.
        found, target = await PeoplePaHttp(creds).people_lookup(client, email, params_template="just_gaia_id")
        if not found or "PROFILE" not in target.sourceIds:
            return {"status": "no_match"}
        # Project the response before any file write. Other containers stay in memory only.
        public = {"personId": target.personId}
        for field in ("sourceIds", "emails", "names", "profilePhotos", "inAppReachability"):
            collection = getattr(target, field, {})
            public[field] = {"PROFILE": collection["PROFILE"]} if "PROFILE" in collection else {}
        public = json.loads(json.dumps(public, cls=GHuntEncoder))
        # Only the normalized public schema is written by the entrypoint below.
        return {"status": "found", "query": email, "profile": public, "stats": {}}


def _worker_entry(output, session):
    import asyncio
    import contextlib
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    email = json.loads(sys.stdin.read(2048)).get("email")
    try:
        with open(os.devnull, "w") as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
            payload = asyncio.run(asyncio.wait_for(_public_worker(email, session), 35))
        if payload.get("status") == "found":
            # Sanitize raw containers to the exact fields consumed by the parser.
            profile = normalize_ghunt(payload, email)
            fields = profile["fields"]
            projected = {"personId": fields["ID"],
                         "sourceIds": {"PROFILE": {"lastUpdated": fields.get("Last profile edit", "")}},
                         "names": {"PROFILE": {"fullname": profile["display_name"]}},
                         "profilePhotos": {"PROFILE": {"url": profile["avatar_url"], "isDefault": False}},
                         "inAppReachability": {"PROFILE": {"apps": profile["lists"].get("Active Google apps", [])}}}
            if "Enterprise user" in fields:
                projected["extendedData"] = {"gplusData": {"isEntrepriseUser": fields["Enterprise user"] == "Yes"}}
            payload = {"status": "found", "query": email, "profile": projected, "stats": profile["stats"]}
    except Exception:
        payload = {"status": "unavailable"}
    encoded = json.dumps(payload).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        encoded = b'{"status":"unavailable"}'
    Path(output).write_bytes(encoded)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        _worker_entry(sys.argv[2], sys.argv[3])
