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
from core import clientip, responses, validation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("myrecon")

_cache = TTLCache(ttl=config.CACHE_TTL)
_limiter = RateLimiter(config.RATE_LIMIT_REQUESTS, config.RATE_LIMIT_WINDOW)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.url_map.strict_slashes = False
    # Every endpoint takes one short string. Without a cap, `get_json(force=True)`
    # will happily allocate whatever is posted, so a single large body is a
    # memory-exhaustion lever on a 512 MB instance. Werkzeug rejects anything
    # over this with a 413 before the body is read.
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_BODY_BYTES
    app.secret_key = config.SECRET_KEY

    _register_cors(app)
    _register_hooks(app)
    _register_routes(app)
    _register_errors(app)
    return app


# ── CORS ─────────────────────────────────────────────────────────

# This API serves JSON and nothing else — no HTML, no scripts, no frames — so
# the policy can be the strictest one there is. It matters despite the absence
# of markup: it is what stops a browser from executing anything should a
# response ever be coaxed into being rendered as a document.
_API_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

# No feature of the browser is needed to read a JSON response.
_API_PERMISSIONS_POLICY = (
    "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
    "magnetometer=(), gyroscope=(), accelerometer=(), interest-cohort=()"
)


def _register_cors(app: Flask) -> None:
    allowed = set(config.ALLOWED_ORIGINS)

    @app.after_request
    def apply_cors(resp):
        origin = request.headers.get("Origin", "")
        if config.CORS_ALLOW_ANY:
            # Literal "*", never a reflection of what was sent. The literal form
            # can't be combined with credentials, which is exactly what makes it
            # safe; reflecting the caller's Origin would hand any site the same
            # access the real frontend has. Production strips "*" in config.py,
            # so this branch is development only.
            resp.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in allowed:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"

        if resp.headers.get("Access-Control-Allow-Origin"):
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Max-Age"] = "86400"

        # Security headers applied to every response, CORS or not.
        resp.headers["Content-Security-Policy"] = _API_CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = _API_PERMISSIONS_POLICY
        # The API is HTTPS-only and always has been, so pinning it costs
        # nothing and removes the first plaintext request from the picture.
        # No preload directive: this host is a subdomain of a domain whose
        # apex preload list entry is managed by the frontend, and claiming
        # preload from here would be claiming it for a domain we don't serve.
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Search engines should not be indexing JSON endpoints.
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        # Stop another origin from pulling API responses into its own process
        # via <img>/<script> side channels (Spectre-style cross-origin reads).
        resp.headers["Cross-Origin-Resource-Policy"] = "same-site"
        return resp


# ── Request hooks: rate limiting ─────────────────────────────────

def _client_ip() -> str:
    """
    The key the rate limiter buckets on.

    Taking `X-Forwarded-For.split(",")[0]` — the previous implementation — read
    the one field in the request the caller writes, so rotating that header made
    the limit vanish. Measured against production before the fix: 34 requests
    with a rotating value, 34x 200. The same 34 without it, 30x 200 then 429.
    core/clientip.py explains the ordering that replaces it.
    """
    return clientip.resolve(
        request.headers,
        request.remote_addr or "",
        trusted_proxy_depth=config.TRUSTED_PROXY_DEPTH,
    )


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
            if (isinstance(value, dict) and value.get("status") != "error"
                    and (name != "email" or value.get("summary", {}).get("breach_status") == "ok")):
                _cache.set(key, value)
            return value
        return wrapper
    return decorator


class PayloadTooLarge(Exception):
    """Body exceeded MAX_BODY_BYTES."""


# The three content types a browser can send cross-origin from a plain <form>
# without asking permission first. Refusing them is what forces a preflight,
# and a preflight is the only thing CORS can actually block.
_SIMPLE_REQUEST_TYPES = (
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
)


class UnsupportedMediaType(Exception):
    """POST arrived without a JSON content type."""


def _require_json_content_type() -> None:
    """
    Insist on `Content-Type: application/json` for writes.

    `get_json(force=True)` parses the body whatever the header says, which
    quietly undoes CORS for requests: any page anywhere can submit a form with
    `enctype="text/plain"` carrying a JSON body, and because that is a "simple
    request" the browser sends it with no preflight and no permission asked.
    The response is unreadable to the attacker — CORS still covers reading —
    but the request lands, which is enough to spend this API's rate limit and
    its outbound quota through someone else's browser.

    Requiring a content type that is not on the simple list means the browser
    must preflight, and the preflight goes through the allowlist in
    `_register_cors`. There is no session or cookie here for a classic CSRF to
    ride, so this closes the remaining half rather than a data-loss hole.
    """
    declared = (request.content_type or "").split(";")[0].strip().lower()
    if declared in _SIMPLE_REQUEST_TYPES or not declared:
        raise UnsupportedMediaType()


def _json_body() -> dict:
    """
    Parse the request body, refusing anything oversized first.

    `MAX_CONTENT_LENGTH` alone is not enough to rely on here. Werkzeug only
    began enforcing it for non-form bodies in 2.3, and `silent=True` swallows
    the 413 it raises when it does — so on an older stack an oversize body was
    parsed in full and on a newer one it came back as an empty dict and a
    confusing 422. Checking the declared length explicitly gives the same answer
    on every version, and a chunked body with no declared length is still capped
    by `MAX_CONTENT_LENGTH` underneath.
    """
    _require_json_content_type()
    declared = request.content_length
    if declared is not None and declared > config.MAX_BODY_BYTES:
        raise PayloadTooLarge()
    return request.get_json(force=True, silent=True) or {}


# ── Routes ───────────────────────────────────────────────────────

def _register_routes(app: Flask) -> None:
    from services.search import search_username, search_fullname
    from services.email import scan_email
    from services.image import scan_image
    from services.network import scan_domain, scan_dns, scan_whois, scan_ip, scan_subdomains
    from services.enrich import enrich_profile
    from modules.wayback import history as wayback_history

    cached_username = cached("username")(search_username)
    cached_fullname = cached("fullname")(search_fullname)
    cached_email = cached("email")(scan_email)
    cached_image = cached("image")(scan_image)
    cached_domain = cached("domain")(scan_domain)
    cached_dns = cached("dns")(scan_dns)
    cached_whois = cached("whois")(scan_whois)
    cached_ip = cached("ip")(scan_ip)
    cached_subdomains = cached("subdomains")(scan_subdomains)
    cached_enrich = cached("enrich")(enrich_profile)

    def _wayback(url: str) -> dict:
        found = wayback_history(url)
        # Being throttled is a temporary failure, not an answer. Tag it so the
        # TTL cache refuses to pin it — otherwise one 429 would be served back
        # as "never archived" for the whole cache window.
        return {"status": "error", **found} if found.get("rate_limited") else found

    cached_wayback = cached("wayback")(_wayback)

    @app.route("/api/health")
    def health():
        return responses.ok({
            "service": config.public_config(),
            # How this caller is identified for rate limiting. It echoes only
            # the caller's own address back to them, which they already know,
            # and the hop count as a bare integer — enough to confirm after a
            # deploy that buckets are per-client, without describing the
            # network in front of the app.
            "client": {
                "resolved_ip": _client_ip(),
                "forwarded_hops": clientip.forwarded_hop_count(request.headers),
            },
        })

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

    @app.route("/api/investigate/stream", methods=["POST", "OPTIONS"])
    def api_investigate_stream():
        """Deep search: a handle correlated into an investigation graph.

        Streamed as NDJSON so the client sees per-platform progress rather than
        a stalled request. Same event shape as /api/username/stream, so the
        frontend reuses one renderer.

        Handles only. Search by personal name was removed — deriving handles
        from a name returned accounts belonging to whoever registered them,
        which is usually not the person searched.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        from services.investigation import investigate

        body = _json_body()
        # validation.username rejects whitespace, so a pasted name is turned
        # away here with a clear message instead of being quietly guessed at.
        query = validation.username(body.get("query", ""))
        deep = validation.boolean(body.get("deep"))

        def generate():
            # investigate() reports progress through a callback, but a
            # generator cannot yield from inside one. Running it on a worker
            # thread and draining a queue is what makes the progress actually
            # live — collecting events into a list and yielding afterwards
            # would deliver the whole scan in one burst at the end, which is
            # indistinguishable from no streaming at all.
            import queue
            import threading

            q: "queue.Queue[dict]" = queue.Queue()
            DONE = {"__done__": True}

            def work():
                try:
                    result = investigate(query, deep=deep, emit=q.put)
                    q.put({"type": "complete", "data": result})
                except Exception as exc:  # noqa: BLE001 - surfaced to client
                    q.put({"type": "error", "error": str(exc)})
                finally:
                    q.put(DONE)

            threading.Thread(target=work, daemon=True).start()
            while True:
                ev = q.get()
                if ev is DONE:
                    return
                yield json.dumps(ev) + "\n"

        resp = Response(stream_with_context(generate()), mimetype="application/x-ndjson")
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["X-Accel-Buffering"] = "no"
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

    @app.route("/api/subdomains", methods=["POST", "OPTIONS"])
    def api_subdomains():
        if request.method == "OPTIONS":
            return ("", 204)
        domain = validation.domain(_json_body().get("domain", ""))
        return responses.ok(cached_subdomains(domain))

    @app.route("/api/image", methods=["POST", "OPTIONS"])
    def api_image():
        if request.method == "OPTIONS":
            return ("", 204)
        body = _json_body()
        url = validation.image_url(body.get("image_url", ""))
        deep = validation.boolean(body.get("deep"))
        return responses.ok(cached_image(url, deep))

    @app.route("/api/enrich", methods=["POST", "OPTIONS"])
    def api_enrich():
        """
        Profile detail for one platform and handle.

        For clients that a platform refuses to answer. The Android sweep runs
        on-device by design, but Instagram blocks by address and a phone that
        has been refused cannot recover on its own — so it asks the server,
        which is usually not the address being refused. Cached, because the
        answer is identical for every caller asking about the same handle.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        body = _json_body()
        platform = validation.platform_name(body.get("platform", ""))
        handle = validation.username(body.get("username", ""))
        return responses.ok(cached_enrich(platform, handle))

    @app.route("/api/wayback", methods=["POST", "OPTIONS"])
    def api_wayback():
        """
        Archive history for a single URL, asked for one result at a time.

        Deliberately not folded into the username scan: the CDX index takes
        ~10s for a cold key and rate-limits under fan-out, so twenty parallel
        lookups return 429s and nothing else. Caching matters more here than
        anywhere — a repeat lookup costs the user nothing and costs
        archive.org nothing.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        url = validation.page_url(_json_body().get("url", ""))
        history = {k: v for k, v in cached_wayback(url).items() if k != "status"}
        return responses.ok({"url": url, "history": history})


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

    @app.errorhandler(413)
    def on_413(_err):
        return responses.error(
            "Request body is too large.", status=413, code="payload_too_large"
        )

    @app.errorhandler(PayloadTooLarge)
    def on_payload_too_large(_err):
        return responses.error(
            "Request body is too large.", status=413, code="payload_too_large"
        )

    @app.errorhandler(UnsupportedMediaType)
    def on_unsupported_media_type(_err):
        return responses.error(
            "Requests must be sent with Content-Type: application/json.",
            status=415, code="unsupported_media_type",
        )

    @app.errorhandler(Exception)
    def on_unexpected(err):
        log.exception("Unhandled error: %s", err)
        return responses.error(
            "An unexpected error occurred. Please try again.",
            status=500, code="server_error",
        )


app = create_app()


if __name__ == "__main__":
    # config.DEBUG is already forced off when FLASK_ENV=production; binding to
    # localhost in that case too means a stray `python app.py` on a server is
    # not also an exposed port.
    host = "0.0.0.0" if config.DEBUG else "127.0.0.1"
    app.run(host=host, port=config.PORT, debug=config.DEBUG)
