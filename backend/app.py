"""
MyRecon API, Flask backend (deploy target: Render).

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
import threading

from flask import Flask, request, g, Response, jsonify, stream_with_context

import config
from core.cache import TTLCache
from core.ratelimit import RateLimiter
from core import clientip, responses, validation
from core.firebase_auth import AuthError, verify_id_token
from core.plans import GuestLimit, NoAllowance

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

# This API serves JSON and nothing else, no HTML, no scripts, no frames, so
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
            # Authorization carries a signed-in user's Firebase ID token. A
            # bearer header, not a cookie, so nothing rides along on a
            # cross-site request and credentials mode stays off.
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
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

    Taking `X-Forwarded-For.split(",")[0]`, the previous implementation, read
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
    The response is unreadable to the attacker, CORS still covers reading,
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
    the 413 it raises when it does, so on an older stack an oversize body was
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


# ── Accounts ─────────────────────────────────────────────────────

class SignInRequired(Exception):
    """This action needs an account."""


class AccountsUnavailable(Exception):
    """Accounts are switched off on this deploy (no store configured)."""


def _signed_in_user():
    """
    The verified Firebase user for this request, or None for a guest.

    A token that is present but bad raises AuthError (401) rather than quietly
    downgrading to guest, so the page refreshes its sign-in instead of silently
    spending the visitor's guest allowance.
    """
    header = request.headers.get("Authorization", "")
    if not header:
        if config.DEV_TEST_ACCOUNT:  # local testing only, see config.py
            return {"sub": "dev-test-user", "email": "dev@localhost", "name": "Dev Test"}
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Malformed Authorization header.")
    return verify_id_token(token.strip())


def _require_user():
    user = _signed_in_user()
    if user is None:
        raise SignInRequired()
    return user


def _scope(body: dict) -> str:
    scope = str(body.get("scope") or "standard").strip().lower()
    if scope not in ("standard", "full"):
        raise validation.ValidationError("scope must be 'standard' or 'full'.")
    return scope


def _admit_scan(scope: str, cached: bool):
    """
    Decide whether this scan may run, charging the allowance it uses.

    Returns (uid, charged) where `charged` names the allowance to refund if
    the scan fails, or None when nothing was charged. Raises SignInRequired,
    AccountsUnavailable, NoAllowance or GuestLimit, each with its own status.
    """
    from core import plans, store

    user = _signed_in_user()
    if scope == "standard":
        if user is None:
            plans.consume_guest_scan(_client_ip())
        return (user or {}).get("sub"), None

    if user is None:
        raise SignInRequired()
    if not store.persistent():
        raise AccountsUnavailable()
    uid = user["sub"]
    account = plans.get_account(uid, user.get("email", ""), user.get("name", ""))
    if cached:
        # Serving a result already in the cache costs nobody anything, so it
        # is not charged, but it is still a full-scan feature.
        if account["full_scans_left"] <= 0:
            raise NoAllowance(account)
        return uid, None
    return uid, plans.consume_full_scan(uid)


# Concurrent 560-platform sweeps in this worker. Each holds 24 sockets.
_full_slots = threading.BoundedSemaphore(max(1, config.FULL_SCAN_SLOTS))


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
        # TTL cache refuses to pin it, otherwise one 429 would be served back
        # as "never archived" for the whole cache window.
        return {"status": "error", **found} if found.get("rate_limited") else found

    cached_wayback = cached("wayback")(_wayback)

    @app.route("/api/health")
    def health():
        return responses.ok({
            "service": config.public_config(),
            # How this caller is identified for rate limiting. It echoes only
            # the caller's own address back to them, which they already know,
            # and the hop count as a bare integer, enough to confirm after a
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
        if _scope(body) == "full":
            from core import plans
            from services.search import _run_full
            key = _cache_key("username_full", username)
            hit = _cache.get(key) if config.CACHE_ENABLED else None
            uid, charged = _admit_scan("full", hit is not None)
            if hit is not None:
                return responses.ok(hit)
            with _full_slots:
                try:
                    data = _run_full(username)
                except Exception:
                    plans.refund_full_scan(uid, charged)
                    raise
            if config.CACHE_ENABLED:
                _cache.set(key, data)
            return responses.ok(data)
        _admit_scan("standard", False)
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
        scope = _scope(body)
        key = (_cache_key("username_full", username) if scope == "full"
               else _cache_key("username", username, deep))
        cached_hit = _cache.get(key) if config.CACHE_ENABLED else None
        # Admitted before the response starts, so a refusal is a real
        # 401/402/429 the page can act on, not an error halfway down a stream.
        uid, charged = _admit_scan(scope, cached_hit is not None)

        def generate():
            from core import plans
            if cached_hit is not None:
                yield json.dumps({"type": "complete", "data": cached_hit}) + "\n"
                return
            slot = _full_slots if scope == "full" else None
            if slot is not None and not slot.acquire(blocking=False):
                yield json.dumps({"type": "progress", "phase": "Queued", "percent": 1,
                                  "detail": "Waiting for a free scan slot…"}) + "\n"
                slot.acquire()
            failed = False
            try:
                for event in stream_username(username, deep, scope):
                    if event.get("type") == "error":
                        failed = True
                    if event.get("type") == "complete":
                        data = event.get("data")
                        if (config.CACHE_ENABLED and isinstance(data, dict)
                                and data.get("status") != "error"):
                            _cache.set(key, data)
                    yield json.dumps(event) + "\n"
            finally:
                if slot is not None:
                    slot.release()
                # A scan that failed is given back. A closed tab is not a
                # failure: the sweep was already running and still counts.
                if charged and failed:
                    plans.refund_full_scan(uid, charged)

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

        Handles only. Search by personal name was removed, deriving handles
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
        # Deep Search runs the standard username scan underneath, so it draws
        # on the same guest allowance.
        _admit_scan("standard", False)

        def generate():
            # investigate() reports progress through a callback, but a
            # generator cannot yield from inside one. Running it on a worker
            # thread and draining a queue is what makes the progress actually
            # live, collecting events into a list and yielding afterwards
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
        has been refused cannot recover on its own, so it asks the server,
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
        anywhere, a repeat lookup costs the user nothing and costs
        archive.org nothing.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        url = validation.page_url(_json_body().get("url", ""))
        history = {k: v for k, v in cached_wayback(url).items() if k != "status"}
        return responses.ok({"url": url, "history": history})

    # ── Accounts & billing ───────────────────────────────────────

    @app.route("/api/plans")
    def api_plans():
        """Public: tiers, limits, and whether sign-in and payments are live."""
        from core import plans, razorpay, store
        return responses.ok({
            # Only ever true on a local development server; see config.py.
            "dev_test_account": config.DEV_TEST_ACCOUNT,
            "accounts_enabled": store.persistent(),
            "payments_enabled": razorpay.enabled() and store.persistent(),
            "razorpay_key_id": config.RAZORPAY_KEY_ID if razorpay.enabled() else None,
            "limits": {
                "standard_platforms": plans.STANDARD_PLATFORMS,
                "full_platforms": plans.FULL_PLATFORMS,
                "guest_scans_per_day": plans.GUEST_SCANS_PER_DAY,
                "free_full_scans_per_week": plans.FREE_FULL_PER_WEEK,
            },
            "plans": list(plans.PLANS.values()),
        })

    @app.route("/api/me")
    def api_me():
        from core import plans, store
        user = _require_user()
        if not store.persistent():
            raise AccountsUnavailable()
        return responses.ok({"account": plans.get_account(
            user["sub"], user.get("email", ""), user.get("name", ""))})

    @app.route("/api/billing/order", methods=["POST", "OPTIONS"])
    def api_billing_order():
        if request.method == "OPTIONS":
            return ("", 204)
        from core import plans, razorpay, store
        user = _require_user()
        if not (razorpay.enabled() and store.persistent()):
            return responses.error("Payments are not open yet.", status=503,
                                   code="payments_unavailable")
        plan_id = str(_json_body().get("plan", "")).strip().lower()
        plan = plans.PLANS.get(plan_id)
        if not plan:
            raise validation.ValidationError("Unknown plan.")
        amount = plan["price_inr"] * 100
        if amount < 100:  # Razorpay's minimum order is 100 paise
            raise validation.ValidationError("Amount is below Razorpay's minimum.")
        try:
            order = razorpay.create_order(
                amount,
                receipt=f"{plan_id}-{user['sub'][:24]}",
                notes={"uid": user["sub"], "plan": plan_id},
            )
        except razorpay.RazorpayAuthError:
            log.error("Razorpay rejected the API keys; check RAZORPAY_KEY_ID/SECRET")
            return responses.error("Payments are misconfigured. Please try later.",
                                   status=401, code="razorpay_auth_failed")
        except razorpay.RazorpayError as exc:
            log.error("Razorpay order creation failed: %s", exc)
            return responses.error("Could not start the payment. Please try again.",
                                   status=500, code="razorpay_error")
        return responses.ok({
            "order_id": order["id"], "amount": order["amount"],
            "currency": order["currency"], "key_id": config.RAZORPAY_KEY_ID,
            "plan": plan, "email": user.get("email", ""), "name": user.get("name", ""),
        })

    def _grant_from_order(order_id: str, expect_uid=None) -> bool:
        """
        Apply the pass an order paid for. Who gets it and which plan are read
        from the order's notes, which only this server writes, never from
        anything the browser sent.
        """
        from core import plans, razorpay
        if not order_id.startswith("order_") or len(order_id) > 40:
            return False
        order = razorpay.fetch_order(order_id)
        notes = order.get("notes") or {}
        uid, plan_id = notes.get("uid"), notes.get("plan")
        if order.get("status") != "paid" or plan_id not in plans.PLANS or not uid:
            return False
        if expect_uid is not None and uid != expect_uid:
            return False
        if int(order.get("amount_paid", 0)) < plans.PLANS[plan_id]["price_inr"] * 100:
            return False
        plans.grant_pass(uid, plan_id, order_id)
        return True

    @app.route("/api/billing/verify", methods=["POST", "OPTIONS"])
    def api_billing_verify():
        if request.method == "OPTIONS":
            return ("", 204)
        from core import plans, razorpay
        user = _require_user()
        body = _json_body()
        order_id = str(body.get("razorpay_order_id", ""))
        payment_id = str(body.get("razorpay_payment_id", ""))
        signature = str(body.get("razorpay_signature", ""))
        if not (order_id and payment_id and signature):
            return responses.error("Missing payment fields.", status=400,
                                   code="payment_fields_missing")
        if not razorpay.payment_signature_ok(order_id, payment_id, signature):
            return responses.error("Payment could not be verified.", status=400,
                                   code="payment_unverified")
        try:
            applied = _grant_from_order(order_id, expect_uid=user["sub"])
        except razorpay.RazorpayError as exc:
            # The signature already proves the payment; the webhook (or a
            # retry) applies the pass once Razorpay answers again.
            log.error("Razorpay order fetch failed during verify: %s", exc)
            applied = False
        # Not applied with a good signature means Razorpay has not marked the
        # order paid yet; the webhook applies it when capture finishes.
        return responses.ok({"applied": applied, "pending": not applied,
                             "account": plans.get_account(user["sub"])})

    @app.route("/api/billing/webhook", methods=["POST"])
    def api_billing_webhook():
        """Razorpay's server-to-server notice. Only the signature is trusted."""
        from core import razorpay
        if request.content_length and request.content_length > config.MAX_BODY_BYTES:
            raise PayloadTooLarge()
        raw = request.get_data(cache=True)
        if not razorpay.webhook_signature_ok(raw, request.headers.get("X-Razorpay-Signature", "")):
            return responses.error("Bad signature.", status=400, code="bad_signature")
        try:
            event = json.loads(raw or b"{}")
        except ValueError:
            return responses.error("Bad payload.", status=400, code="bad_payload")
        payload = event.get("payload") or {}
        order_id = (((payload.get("order") or {}).get("entity") or {}).get("id")
                    or ((payload.get("payment") or {}).get("entity") or {}).get("order_id"))
        if event.get("event") in ("order.paid", "payment.captured") and order_id:
            _grant_from_order(order_id)
        # 200 once the signature checks out, whatever happened, or Razorpay
        # retries the same event for a day.
        return responses.ok({"received": True})


# ── Error handling ───────────────────────────────────────────────

def _register_errors(app: Flask) -> None:
    @app.errorhandler(validation.ValidationError)
    def on_validation_error(err):
        return responses.error(str(err), status=422, code="invalid_input")

    @app.errorhandler(AuthError)
    def on_auth_error(err):
        return responses.error(str(err), status=401, code="auth_invalid")

    @app.errorhandler(SignInRequired)
    def on_sign_in_required(_err):
        return responses.error(
            "Sign in (free) to run the full scan.", status=401, code="sign_in_required",
        )

    @app.errorhandler(AccountsUnavailable)
    def on_accounts_unavailable(_err):
        return responses.error(
            "Accounts are not switched on yet. The standard scan still works.",
            status=503, code="accounts_unavailable",
        )

    @app.errorhandler(GuestLimit)
    def on_guest_limit(_err):
        return responses.error(
            f"Guests get {config.GUEST_SCANS_PER_DAY} scans a day. "
            "Sign in free to keep going.",
            status=429, code="guest_limit",
        )

    @app.errorhandler(NoAllowance)
    def on_no_allowance(err):
        return jsonify({
            "status": "error", "code": "upgrade_required",
            "error": "You have used this week's free full scans. Pro passes add more.",
            "account": err.entitlements,
        }), 402

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
