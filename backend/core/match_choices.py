"""Private user assertions, separate from provider evidence and shared caches."""
import hashlib
import time
from urllib.parse import urlsplit, urlunsplit

from core import store


def canonical_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("A valid profile URL is required.")
    try:
        url = urlsplit(value.strip())
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError()
        from core.profile_input import parse_profile_input
        try:
            parsed = parse_profile_input(value)
            if parsed.get("url"):
                return parsed["url"]
        except ValueError:
            pass
        # Preserve path case and query: they can identify different accounts.
        return urlunsplit((url.scheme, url.netloc.lower(), url.path or "/", url.query, ""))
    except ValueError:
        raise ValueError("A valid profile URL is required.") from None


def choices(uid):
    return {}


def save(uid, url, choice, cleanup=None):
    canonical_url(url)
    if choice not in ("mine", "not_mine", "unsure", ""):
        raise ValueError("Choose mine, not mine, or unsure.")
    if cleanup not in (None, "review", "keep", "requested", "completed"):
        raise ValueError("Choose a supported cleanup state.")
    # The browser keeps these assertions only in its current page memory.
    return {}
