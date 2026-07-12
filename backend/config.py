"""
MyRecon — Backend configuration.

All configuration is read from environment variables. No secrets are ever
committed to the repository. See `.env.example` for the full list.
"""

import os


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ── Branding ─────────────────────────────────────────────────────
APP_NAME = os.environ.get("APP_NAME", "MyRecon")
APP_DOMAIN = os.environ.get("APP_DOMAIN", "myrecon.xyz")

# ── Server ───────────────────────────────────────────────────────
ENV = os.environ.get("FLASK_ENV", "production")
DEBUG = _get_bool("FLASK_DEBUG", ENV != "production")
PORT = _get_int("PORT", 5000)
SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()

# ── CORS ─────────────────────────────────────────────────────────
# Comma-separated list of allowed frontend origins. In development we fall
# back to permissive localhost origins so the tool works out of the box.
_DEFAULT_ORIGINS = (
    "https://myrecon.xyz,https://www.myrecon.xyz"
    if ENV == "production"
    else "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:8000"
)
ALLOWED_ORIGINS = _get_list("ALLOWED_ORIGINS", _DEFAULT_ORIGINS)

# ── Third-party API keys (all optional) ──────────────────────────
# The app degrades gracefully when a key is missing.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX_ID = os.environ.get("GOOGLE_CX_ID", "")
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "")

# ── Rate limiting ────────────────────────────────────────────────
RATE_LIMIT_ENABLED = _get_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_REQUESTS = _get_int("RATE_LIMIT_REQUESTS", 30)   # requests
RATE_LIMIT_WINDOW = _get_int("RATE_LIMIT_WINDOW", 60)       # seconds

# ── Caching ──────────────────────────────────────────────────────
CACHE_ENABLED = _get_bool("CACHE_ENABLED", True)
CACHE_TTL = _get_int("CACHE_TTL", 600)                      # seconds

# ── Scan tuning ──────────────────────────────────────────────────
SCAN_MAX_WORKERS = _get_int("SCAN_MAX_WORKERS", 20)
REQUEST_TIMEOUT = _get_int("REQUEST_TIMEOUT", 10)


def public_config() -> dict:
    """Non-sensitive config exposed via /api/health for diagnostics."""
    return {
        "app": APP_NAME,
        "domain": APP_DOMAIN,
        "env": ENV,
        "features": {
            "google_search": bool(GOOGLE_API_KEY and GOOGLE_CX_ID),
            "hibp": bool(HIBP_API_KEY),
            "rate_limit": RATE_LIMIT_ENABLED,
            "cache": CACHE_ENABLED,
        },
    }
