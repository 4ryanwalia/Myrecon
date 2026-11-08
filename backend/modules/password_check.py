"""
Password exposure check via Pwned Passwords k-anonymity range API.

Mirrors the browser implementation in `frontend/assets/js/app.js` so the CLI
and website produce the same verdict, breach count, and brute-force resistance
estimate without ever transmitting the password or its full hash.

How k-anonymity works here:
  1. Hash the password locally with SHA-1 (uppercase hex, 40 characters).
  2. Send only the first 5 hex characters to `api.pwnedpasswords.com/range/`
     with `Add-Padding: true`.
  3. Match the remaining 35-character suffix locally against the response rows.

Neither the plaintext password nor the full SHA-1 digest ever leaves the
machine, and neither is included in the returned dictionary (so `--json`
redirection cannot leak the secret either).
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import requests

PWNED_RANGE_URL = "https://api.pwnedpasswords.com/range/"
_TIMEOUT = 10
_HEADERS = {
    "Add-Padding": "true",
    "User-Agent": "MyRecon/1.0",
}


def _human_duration(seconds: float) -> str:
    """Format an offline crack estimate using the same scale as the web UI."""
    if seconds < 1:
        return "instantly"
    units = (
        ("second", 60.0),
        ("minute", 60.0),
        ("hour", 24.0),
        ("day", 365.0),
    )
    value = seconds
    for name, step in units:
        if value < step:
            n = int(round(value))
            return f"{n:,} {name}{'' if n == 1 else 's'}"
        value /= step
    if math.isinf(value) or value >= 1e9:
        return "centuries"
    n = int(round(value))
    return f"{n:,} year{'' if n == 1 else 's'}"


def password_strength(password: str) -> dict[str, Any]:
    """
    Entropy from the character pool actually used.

    Measures resistance to offline brute force only (~100 billion guesses/sec,
    a mid-range GPU rig attacking a fast hash). A breached password is weak at
    any entropy, which is why the corpus result always outranks this number.
    """
    has_lower = any("a" <= c <= "z" for c in password)
    has_upper = any("A" <= c <= "Z" for c in password)
    has_digit = any("0" <= c <= "9" for c in password)
    has_symbol = any(
        not (("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9"))
        for c in password
    )
    pool = (
        (26 if has_lower else 0)
        + (26 if has_upper else 0)
        + (10 if has_digit else 0)
        + (33 if has_symbol else 0)
    )
    bits = len(password) * math.log2(pool or 1)
    if bits <= 0:
        seconds = 0.0
    elif bits > 500:
        seconds = float("inf")
    else:
        seconds = (2.0 ** (bits - 1)) / 1e11

    label = "Very weak"
    if bits >= 100:
        label = "Excellent"
    elif bits >= 75:
        label = "Strong"
    elif bits >= 60:
        label = "Reasonable"
    elif bits >= 40:
        label = "Weak"

    return {
        "bits": int(round(bits)),
        "label": label,
        "crack": _human_duration(seconds),
        "pool": pool,
        "length": len(password),
    }


def pwned_count(password: str, timeout: int = _TIMEOUT) -> tuple[str, int]:
    """
    Query `api.pwnedpasswords.com/range/<prefix>` and return `(prefix, count)`.

    Only the 5-character SHA-1 prefix is sent. Padding rows returned by the API
    carry a count of 0 and are treated as non-matches.
    """
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]

    resp = requests.get(
        f"{PWNED_RANGE_URL}{prefix}",
        headers=_HEADERS,
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Breach corpus is unavailable right now (HTTP {resp.status_code})."
        )

    for raw_line in resp.text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        suf, _, cnt_str = line.partition(":")
        if suf.strip().upper() == suffix:
            try:
                return prefix, max(0, int(cnt_str.strip()))
            except ValueError:
                return prefix, 0
    return prefix, 0


def check_password(password: str) -> dict[str, Any]:
    """
    Full k-anonymity password breach check and local strength estimate.

    Raises `ValueError` if `password` is empty. Network or upstream failures
    return `{"status": "error", "error": ...}` so an unreachable corpus is
    never mistaken for a clean password.
    """
    if not isinstance(password, str) or len(password) == 0:
        raise ValueError("Password is required.")

    strength = password_strength(password)
    try:
        prefix, count = pwned_count(password)
    except (requests.RequestException, RuntimeError) as exc:
        return {
            "status": "error",
            "error": str(exc) or "Could not reach Pwned Passwords.",
        }

    breached = count > 0
    advice = (
        "Stop using this password everywhere it appears. Attackers load "
        "exactly these lists into credential-stuffing tools, so its strength "
        "on paper no longer matters."
        if breached
        else "This password isn't in the corpus. That means it hasn't turned "
        "up in a known dump — it doesn't by itself mean the password is strong."
    )

    return {
        "status": "ok",
        "breached": breached,
        "count": count,
        "sha1_prefix": prefix,
        "strength": strength,
        "advice": advice,
        "privacy": {
            "source": "Pwned Passwords",
            "k_anonymity": True,
            "prefix_sent": prefix,
            "note": (
                "Hashed locally with SHA-1; only the 5-character prefix was "
                "sent to api.pwnedpasswords.com/range/."
            ),
        },
    }
