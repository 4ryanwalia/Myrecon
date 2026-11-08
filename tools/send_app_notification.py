"""Private MyRecon FCM sender. Preview by default; --send explicitly broadcasts."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import sys
import time

PROJECT = "myrecon-bugsnaps"
TOPIC = "myrecon_announcements"
CHANNEL = "app_announcements"


def build_payload(title, body, *, debug=False, token=None, validate=False):
    title, body = title.strip(), body.strip()
    if not title or len(title) > 120:
        raise ValueError("Title must contain 1–120 characters.")
    if not body or len(body) > 1800:
        raise ValueError("Body must contain 1–1800 characters.")
    message = {
        "notification": {"title": title, "body": body},
        "android": {
            "priority": "HIGH",
            "ttl": "86400s",
            "notification": {"channel_id": CHANNEL, "icon": "ic_stat_recon"},
        },
    }
    if token:
        if token != token.strip() or not token.strip():
            raise ValueError("Invalid device token.")
        message["token"] = token
    else:
        message["topic"] = TOPIC + ("_debug" if debug else "")
    payload = {"validate_only": validate, "message": message}
    if len(json.dumps(message, ensure_ascii=False).encode("utf-8")) > 3500:
        raise ValueError("Message is too large in UTF-8. Shorten the title or body.")
    return payload


def load_credentials():
    # Same JSON/base64 format as the backend; also support Google's file convention.
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if raw:
        if not raw.startswith("{"):
            raw = base64.b64decode(raw).decode("utf-8")
        credentials = json.loads(raw)
    else:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not path:
            raise ValueError("Set FIREBASE_SERVICE_ACCOUNT or GOOGLE_APPLICATION_CREDENTIALS to a private service-account file.")
        credentials = json.loads(Path(path).read_text(encoding="utf-8"))
    if credentials.get("project_id") != PROJECT:
        raise ValueError("Credentials must belong to the myrecon-bugsnaps project.")
    if not credentials.get("client_email") or not credentials.get("private_key"):
        raise ValueError("Service-account credentials are incomplete.")
    return credentials


def deliver(payload, credentials):
    # Loaded only for a real request: a preview needs no credentials or packages.
    import jwt
    import requests

    now = int(time.time())
    assertion = jwt.encode({
        "iss": credentials["client_email"],
        "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now, "exp": now + 3600,
    }, credentials["private_key"], algorithm="RS256")
    auth = requests.post("https://oauth2.googleapis.com/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion,
    }, timeout=20)
    auth.raise_for_status()
    response = requests.post(
        f"https://fcm.googleapis.com/v1/projects/{PROJECT}/messages:send",
        headers={"Authorization": "Bearer " + auth.json()["access_token"]},
        json=payload, timeout=30,
    )
    if not response.ok:
        # Do not dump response/request bodies: they may contain device identifiers.
        try:
            status = response.json().get("error", {}).get("status", "UNKNOWN")
        except ValueError:
            status = "UNKNOWN"
        if not re.fullmatch(r"[A-Z_]+", str(status)):
            status = "UNKNOWN"
        raise ValueError(f"FCM rejected the request (HTTP {response.status_code}, {status}). Check API enablement and Cloud Messaging permissions.")
    return response.json()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--debug", action="store_true", help="Target debug installations only")
    target.add_argument("--token", help="Target a single test installation instead of the topic")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--send", action="store_true", help="Actually send the notification")
    mode.add_argument("--validate", action="store_true", help="Ask FCM to validate without delivering")
    args = parser.parse_args(argv)
    try:
        payload = build_payload(args.title, args.body, debug=args.debug, token=args.token, validate=args.validate)
        if not args.send and not args.validate:
            # Device tokens are private; don't print them in preview output.
            preview = json.loads(json.dumps(payload))
            if "token" in preview["message"]:
                preview["message"]["token"] = "<single device token>"
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            print("Preview only. No network requests. Add --validate to check with FCM or --send to deliver.")
            return 0
        result = deliver(payload, load_credentials())
        if args.validate:
            print("FCM validation passed. No notification was delivered.")
        else:
            print("FCM accepted the message: " + result.get("name", "(no message ID)"))
            print("Acceptance does not confirm delivery to individual phones.")
        return 0
    except Exception as exc:
        # Avoid traceback/token/private-key leakage from third-party exceptions.
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            print(f"Error: {exc}", file=sys.stderr)
        else:
            print(f"Notification request failed ({type(exc).__name__}). Check credentials and connectivity.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
