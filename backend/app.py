"""
MyRecon API — Flask backend (deploy target: Render).

A stateless JSON API. All heavy OSINT work lives in `services/` and
`modules/`; this file is only routing, validation, CORS, rate limiting,
caching, and error handling.

Run locally:   python app.py
Run on Render: gunicorn wsgi:app  (see Procfile)
"""

import functools
import hashlib
import json
import logging

from flask import Flask, request, g, Response, stream_with_context

import config
from core.cache import TTLCache
from core.ratelimit import RateLimiter
from core import responses, validation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("myrecon")

_cache = TTLCache(ttl=config.CACHE_TTL)
_limiter = RateLimiter(config.RATE_LIMIT_REQUESTS, config.RATE_LIMIT_WINDOW)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.url_map.strict_slashes = False

    _register_cors(app)
    _register_hooks(app)
    _register_routes(app)
    _register_errors(app)
    return app


# ── CORS ─────────────────────────────────────────────────────────

def _register_cors(app: Flask) -> None:
    allowed = set(config.ALLOWED_ORIGINS)

    @app.after_request
    def apply_cors(resp):
        origin = request.headers.get("Origin", "")
        if origin and (origin in allowed or "*" in allowed):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Max-Age"] = "86400"
        # Security headers applied to every response.
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp


# ── Request hooks: rate limiting ─────────────────────────────────

def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _register_hooks(app: Flask) -> None:
    @app.before_request
    def rate_limit():
        if not config.RATE_LIMIT_ENABLED:
            return None
        if request.method == "OPTIONS" or request.path == "/api/health":
            return None
        if not request.path.startswith("/api/"):
            return None
        allowed, retry_after = _limiter.check(_client_ip())
        if not allowed:
            resp = responses.error(
                "Rate limit exceeded. Please slow down and try again shortly.",
                status=429, code="rate_limited",
            )
            resp[0].headers["Retry-After"] = str(retry_after)
            return resp
        return None


# ── Caching helper ───────────────────────────────────────────────

def _cache_key(name: str, *parts) -> str:
    raw = "|".join([name, *[str(p) for p in parts]])
    return hashlib.sha256(raw.encode()).hexdigest()


def cached(name: str):
    """Wrap a producer with the TTL cache keyed on its arguments."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args):
            if not config.CACHE_ENABLED:
                return fn(*args)
            key = _cache_key(name, *args)
            hit = _cache.get(key)
            if hit is not None:
                return hit
            value = fn(*args)
            # Never cache soft errors.
            if isinstance(value, dict) and value.get("status") != "error":
                _cache.set(key, value)
            return value
        return wrapper
    return decorator


def _json_body() -> dict:
    return request.get_json(force=True, silent=True) or {}


# ── Routes ───────────────────────────────────────────────────────

def _register_routes(app: Flask) -> None:
    from services.search import search_username, search_fullname
    from services.email import scan_email
    from services.image import scan_image
    from services.network import scan_domain, scan_dns, scan_whois, scan_ip

    cached_username = cached("username")(search_username)
    cached_fullname = cached("fullname")(search_fullname)
    cached_email = cached("email")(scan_email)
    cached_image = cached("image")(scan_image)
    cached_domain = cached("domain")(scan_domain)
    cached_dns = cached("dns")(scan_dns)
    cached_whois = cached("whois")(scan_whois)
    cached_ip = cached("ip")(scan_ip)

    @app.route("/api/health")
    def health():
        return responses.ok({"service": config.public_config()})

    @app.route("/api/username", methods=["POST", "OPTIONS"])
    def api_username():
        if request.method == "OPTIONS":
            return ("", 204)
        body = _json_body()
        username = validation.username(body.get("username", ""))
        deep = validation.boolean(body.get("deep"))
        return responses.ok(cached_username(username, deep))

    @app.route("/api/username/stream", methods=["POST", "OPTIONS"])
    def api_username_stream():
        """Live username scan streamed as newline-delimited JSON (NDJSON).

        Emits {"type":"progress",...} events during the scan and a final
        {"type":"complete","data":{...}} with the full result. Shares the
        TTL cache with the non-streaming /api/username endpoint.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        from services.search import stream_username

        body = _json_body()
        username = validation.username(body.get("username", ""))
        deep = validation.boolean(body.get("deep"))
        key = _cache_key("username", username, deep)
        cached_hit = _cache.get(key) if config.CACHE_ENABLED else None

        def generate():
            if cached_hit is not None:
                yield json.dumps({"type": "complete", "data": cached_hit}) + "\n"
                return
            for event in stream_username(username, deep):
                if event.get("type") == "complete" and config.CACHE_ENABLED:
                    data = event.get("data")
                    if isinstance(data, dict) and data.get("status") != "error":
                        _cache.set(key, data)
                yield json.dumps(event) + "\n"

        resp = Response(stream_with_context(generate()), mimetype="application/x-ndjson")
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["X-Accel-Buffering"] = "no"  # disable proxy buffering
        return resp

    @app.route("/api/fullname", methods=["POST", "OPTIONS"])
    def api_fullname():
        if request.method == "OPTIONS":
            return ("", 204)
        body = _json_body()
        name = validation.full_name(body.get("full_name", ""))
        deep = validation.boolean(body.get("deep"))
        return responses.ok(cached_fullname(name, deep))

    @app.route("/api/email", methods=["POST", "OPTIONS"])
    def api_email():
        if request.method == "OPTIONS":
            return ("", 204)
        body = _json_body()
        email = validation.email(body.get("email", ""))
        return responses.ok(cached_email(email))

    @app.route("/api/domain", methods=["POST", "OPTIONS"])
    def api_domain():
        if request.method == "OPTIONS":
            return ("", 204)
        domain = validation.domain(_json_body().get("domain", ""))
        return responses.ok(cached_domain(domain))

    @app.route("/api/dns", methods=["POST", "OPTIONS"])
    def api_dns():
        if request.method == "OPTIONS":
            return ("", 204)
        domain = validation.domain(_json_body().get("domain", ""))
        return responses.ok(cached_dns(domain))

    @app.route("/api/whois", methods=["POST", "OPTIONS"])
    def api_whois():
        if request.method == "OPTIONS":
            return ("", 204)
        domain = validation.domain(_json_body().get("domain", ""))
        return responses.ok(cached_whois(domain))

    @app.route("/api/ip", methods=["POST", "OPTIONS"])
    def api_ip():
        if request.method == "OPTIONS":
            return ("", 204)
        ip = validation.ip_address(_json_body().get("ip", ""))
        return responses.ok(cached_ip(ip))

    @app.route("/api/image", methods=["POST", "OPTIONS"])
    def api_image():
        if request.method == "OPTIONS":
            return ("", 204)
        body = _json_body()
        url = validation.image_url(body.get("image_url", ""))
        deep = validation.boolean(body.get("deep"))
        return responses.ok(cached_image(url, deep))


# ── Error handling ───────────────────────────────────────────────

def _register_errors(app: Flask) -> None:
    @app.errorhandler(validation.ValidationError)
    def on_validation_error(err):
        return responses.error(str(err), status=422, code="invalid_input")

    @app.errorhandler(404)
    def on_404(_err):
        return responses.error("Not found.", status=404, code="not_found")

    @app.errorhandler(405)
    def on_405(_err):
        return responses.error("Method not allowed.", status=405, code="method_not_allowed")

    @app.errorhandler(Exception)
    def on_unexpected(err):
        log.exception("Unhandled error: %s", err)
        return responses.error(
            "An unexpected error occurred. Please try again.",
            status=500, code="server_error",
        )


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
