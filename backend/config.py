"""
MyRecon — Backend configuration.

All configuration is read from environment variables. No secrets are ever
committed to the repository. See `.env.example` for the full list.
"""

import logging
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
IS_PRODUCTION = ENV == "production"

# Debug is force-off in production rather than merely defaulted off. Flask's
# debugger is an interactive Python console on an unhandled exception; one
# stray FLASK_DEBUG=1 in a dashboard would otherwise be remote code execution,
# and that is too large a consequence to leave resting on an env var nobody
# audits.
DEBUG = False if IS_PRODUCTION else _get_bool("FLASK_DEBUG", True)

PORT = _get_int("PORT", 5000)

# A random fallback key is fine for a dev run and wrong in production, where two
# gunicorn workers would generate two different keys and anything signed by one
# would be rejected by the other. Nothing is signed today; the guard is here so
# that stays a deliberate choice rather than a silent breakage the first time a
# session or a signed token is added.
SECRET_KEY = os.environ.get("SECRET_KEY") or ""
SECRET_KEY_IS_EPHEMERAL = not SECRET_KEY
if SECRET_KEY_IS_EPHEMERAL:
    SECRET_KEY = os.urandom(32).hex()
    if IS_PRODUCTION:
        # Deliberately a warning and not a raise. Nothing is signed with this
        # key today, so refusing to boot would trade a latent problem for a
        # certain outage on the next deploy. `/api/health` reports the state so
        # it is visible, and app.py escalates to a hard failure the moment a
        # signed session actually exists.
        logging.getLogger("myrecon.config").error(
            "SECRET_KEY is not set: using a per-worker random key. Nothing is "
            "signed today so this is not yet exploitable, but set SECRET_KEY in "
            "the Render dashboard before adding sessions or signed tokens."
        )

# ── Request limits ───────────────────────────────────────────────
# Every endpoint takes a single short string, so a body past a few KB is either
# a mistake or an attempt to make the JSON parser allocate. Flask returns 413
# before reading the body when this is set.
MAX_BODY_BYTES = _get_int("MAX_BODY_BYTES", 64 * 1024)

# Hops in front of this app that append to X-Forwarded-For. 0 is correct behind
# a single edge (Render, Cloudflare); raise it only if you add another proxy.
# See core/clientip.py for why the left of that header cannot be trusted.
TRUSTED_PROXY_DEPTH = _get_int("TRUSTED_PROXY_DEPTH", 0)

# ── CORS ─────────────────────────────────────────────────────────
# Comma-separated list of allowed frontend origins. In development we fall
# back to permissive localhost origins so the tool works out of the box.
_DEFAULT_ORIGINS = (
    "https://myrecon.xyz,https://www.myrecon.xyz"
    if ENV == "production"
    else "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:8000"
)
ALLOWED_ORIGINS = _get_list("ALLOWED_ORIGINS", _DEFAULT_ORIGINS)

# Reflecting an arbitrary Origin back as Access-Control-Allow-Origin is what
# turns a "*" in config into a same-origin bypass for every browser that sends
# one. If a wildcard is genuinely wanted, it is emitted literally instead — a
# literal "*" cannot be paired with credentials, which is the property that
# makes it safe. Production refuses the wildcard outright.
CORS_ALLOW_ANY = "*" in ALLOWED_ORIGINS
if CORS_ALLOW_ANY and IS_PRODUCTION:
    # Drop the wildcard rather than refuse to boot: denying unlisted origins is
    # the fail-safe direction, and the deployed config already names its two
    # origins explicitly, so this changes nothing unless someone loosens it.
    ALLOWED_ORIGINS = [o for o in ALLOWED_ORIGINS if o != "*"]
    CORS_ALLOW_ANY = False
    logging.getLogger("myrecon.config").error(
        'ALLOWED_ORIGINS contained "*", which is ignored in production. List '
        "the exact frontend origins instead."
    )

# ── Third-party API keys (all optional) ──────────────────────────
# The app degrades gracefully when a key is missing.
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX_ID = os.environ.get("GOOGLE_CX_ID", "")
# HIBP_API_KEY was here and has been removed. Have I Been Pwned is the only
# breach source that needs a paid subscription, and XposedOrNot's check-email
# endpoint answers the same question for free — see EmailLookup in
# modules/email_lookup.py. Nothing reads the variable any more; unset it in the
# deploy environment.

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
            "rate_limit": RATE_LIMIT_ENABLED,
            "cache": CACHE_ENABLED,
        },
        # Surfaced so a misconfigured deploy is visible without shell access.
        # It reports only whether a key was supplied, never the key.
        "secret_key_configured": not SECRET_KEY_IS_EPHEMERAL,
    }
