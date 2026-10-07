"""Private bundled worker. Never imports or executes reference-project files.

Selected endpoint/metadata mappings adapted from User Scanner (MIT, Kaif 2025).
See docs/licenses/user-scanner-MIT.txt. Deliberately excludes HTML fallbacks,
recovery/login/sign-up requests, cross-scans, cookies and credential submission.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

# -I ignores environment Python paths; only our bundled backend is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.user_scanner_registry import REGISTRY, MAX_OUTPUT, MODULE_SECONDS, outcome

MAX_BODY = 262_144


def fetch(spec, url, deadline):
    import requests
    from core.netguard import safe_get
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise requests.Timeout()
    with safe_get(url, stream=True, timeout=(min(3, remaining), min(3, remaining)),
                  allowed_hosts=spec.hosts, redirect_limit=0,
                  headers={"User-Agent": "MyRecon-Public-Profile-Adapter", "Accept": "application/json"}) as response:
        chunks, size = [], 0
        for chunk in response.iter_content(8192):
            size += len(chunk)
            if time.monotonic() >= deadline:
                raise requests.Timeout()
            if size > MAX_BODY:
                raise ValueError("response limit")
            chunks.append(chunk)
        # Blocked/rate-limited statuses cannot become absent, even with JSON.
        code = response.status_code
        if code == 429 or (code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"):
            return code, None, "rate_limited"
        if code in (401, 403, 407, 423, 451) or code >= 500:
            return code, None, "unavailable"
        try:
            data = json.loads(b"".join(chunks))
        except (ValueError, UnicodeError):
            data = None
        return code, data, None


def github(spec, target, deadline):
    code, data, failure = fetch(spec, "https://api.github.com/users/" + target, deadline)
    if failure:
        return outcome(spec, failure, "Provider blocked, rate-limited or failed the check", status_code=code)
    if (code == 200 and isinstance(data, dict) and type(data.get("id")) is int
            and isinstance(data.get("login"), str) and data["login"].casefold() == target.casefold()
            and data.get("type") in ("User", "Organization")):
        return outcome(spec, "found", "Public API confirmed this exact handle", metadata=data,
                       url="https://github.com/" + target, status_code=code)
    if code == 404 and isinstance(data, dict) and data.get("message") == "Not Found":
        return outcome(spec, "not_found", "Public API explicitly reported no such handle", status_code=code)
    return outcome(spec, "unavailable", "Provider returned ambiguous or mismatched evidence", status_code=code)


def gravatar(spec, target, deadline):
    encoded = target.strip().lower().encode()
    hashes = (hashlib.sha256(encoded).hexdigest(), hashlib.md5(encoded).hexdigest())
    for digest in hashes:
        code, data, failure = fetch(spec, "https://en.gravatar.com/" + digest + ".json", deadline)
        if failure:
            return outcome(spec, failure, "Provider blocked, rate-limited or failed the check", status_code=code)
        entries = data.get("entry") if isinstance(data, dict) else None
        if code == 200 and isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict):
            entry = entries[0]
            if entry.get("hash") not in hashes:
                return outcome(spec, "unavailable", "Public profile hash did not match the queried email", status_code=code)
            metadata = {"display_name": entry.get("displayName"), "username": entry.get("preferredUsername"),
                        "bio": entry.get("aboutMe"), "location": entry.get("currentLocation")}
            return outcome(spec, "found", "Public profile matched the email hash; ownership is not verified",
                           metadata=metadata, status_code=code)
        if code != 404:
            return outcome(spec, "unavailable", "Provider returned ambiguous profile evidence", status_code=code)
    return outcome(spec, "unavailable", "No readable public profile; this does not establish account absence")


HANDLERS = {"username.github": github, "email.gravatar": gravatar}


def main():
    spec = None
    try:
        request = json.loads(sys.stdin.buffer.read(2049))
        spec = REGISTRY.get(request.get("id"))
        if spec is None:
            return 1
        from modules.user_scanner import _valid_target
        if not spec.enabled or not _valid_target(request.get("target"), spec.scan_type):
            row = outcome(spec, "skipped", "Optional module is disabled or target is unsupported")
        else:
            try:
                import requests
                from core.netguard import BlockedRequest
                row = HANDLERS[spec.id](spec, request["target"], time.monotonic() + MODULE_SECONDS)
            except ImportError:
                row = outcome(spec, "unavailable", "Optional transport dependency is missing")
            except requests.Timeout:
                row = outcome(spec, "timeout", "Optional request reached its deadline")
            except BlockedRequest:
                row = outcome(spec, "unavailable", "Network policy blocked the optional request")
            except Exception:
                row = outcome(spec, "unavailable", "Optional provider returned unusable evidence")
        encoded = json.dumps(row, ensure_ascii=True).encode()
        if len(encoded) > MAX_OUTPUT:
            encoded = json.dumps(outcome(spec, "unavailable", "Optional output exceeded its limit")).encode()
        sys.stdout.buffer.write(encoded)
        return 0
    except Exception:
        # Do not echo exceptions, provider bodies, query strings or credentials.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
