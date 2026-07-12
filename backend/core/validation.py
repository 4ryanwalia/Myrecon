"""
Input validation and sanitization.

Every user-supplied value is validated here before it reaches a network call.
Validators raise `ValidationError` with a safe, user-facing message.
"""

import ipaddress
import re


class ValidationError(ValueError):
    """Raised when user input fails validation. Message is safe to surface."""


# ── Patterns ─────────────────────────────────────────────────────
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._@\-]{1,64}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9\-]{1,63}(?<!-)"
    r"(\.(?!-)[A-Za-z0-9\-]{1,63}(?<!-))+$"
)
_FULLNAME_RE = re.compile(r"^[\w .'\-]{2,80}$", re.UNICODE)


def _strip(value, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"'{field}' must be a string.")
    value = value.strip()
    if not value:
        raise ValidationError(f"'{field}' is required.")
    if len(value) > 256:
        raise ValidationError(f"'{field}' is too long.")
    # Reject control characters early.
    if any(ord(c) < 32 for c in value):
        raise ValidationError(f"'{field}' contains invalid characters.")
    return value


def username(value: str) -> str:
    value = _strip(value, "username")
    # Allow a pasted profile URL — extract the final path segment.
    if value.lower().startswith(("http://", "https://")):
        value = value.rstrip("/").split("/")[-1]
    value = value.lstrip("@")
    if not _USERNAME_RE.match(value):
        raise ValidationError(
            "Username may only contain letters, numbers, and . _ - @ characters."
        )
    return value


def full_name(value: str) -> str:
    value = _strip(value, "full name")
    if not _FULLNAME_RE.match(value):
        raise ValidationError("Please enter a valid name.")
    return value


def email(value: str) -> str:
    value = _strip(value, "email").lower()
    if not _EMAIL_RE.match(value) or len(value) > 254:
        raise ValidationError("Please enter a valid email address.")
    return value


def domain(value: str) -> str:
    value = _strip(value, "domain").lower()
    # Accept a full URL and reduce to its hostname.
    value = re.sub(r"^[a-z]+://", "", value)
    value = value.split("/")[0].split("?")[0].split("#")[0]
    value = value.split(":")[0]  # strip port
    value = value.lstrip(".")
    if value.startswith("www."):
        value = value[4:]
    if not _DOMAIN_RE.match(value):
        raise ValidationError("Please enter a valid domain, e.g. example.com.")
    return value


def ip_address(value: str) -> str:
    value = _strip(value, "IP address")
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError("Please enter a valid IPv4 or IPv6 address.")
    if parsed.is_private or parsed.is_loopback or parsed.is_reserved:
        raise ValidationError("Private, loopback, and reserved addresses are not supported.")
    return str(parsed)


def image_url(value: str) -> str:
    value = _strip(value, "image URL")
    if not re.match(r"^https?://", value, re.IGNORECASE):
        raise ValidationError("Image URL must start with http:// or https://.")
    if len(value) > 2048:
        raise ValidationError("Image URL is too long.")
    return value


def boolean(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default
