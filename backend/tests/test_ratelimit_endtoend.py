"""
End-to-end proof that the rate limiter cannot be bypassed with a header.

The WSGI environ is built by hand rather than through Flask's test client,
because the client shipped with older Werkzeug never populates REMOTE_ADDR —
which silently turns every "direct connection" case into the proxied one and
hides exactly the behaviour these tests exist to pin down.

The measurement being reproduced, taken against production before the fix:

    rotating X-Forwarded-For  -> 34 requests, 34x 200, zero 429
    no header at all          -> 34 requests, 30x 200 then 429
"""

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import app as appmod  # noqa: E402
import config  # noqa: E402

CLIENT = "93.184.216.34"


@pytest.fixture(autouse=True)
def fresh_limiter():
    """A limiter with no history, so cases cannot contaminate each other."""
    appmod._limiter._hits.clear()
    appmod._cache.clear()
    yield
    appmod._limiter._hits.clear()


def call(path="/api/dns", body=None, remote_addr="", headers=None):
    """Invoke the WSGI app directly and return (status_code, headers)."""
    payload = json.dumps(body if body is not None else {"domain": "example.com"}).encode()
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": path,
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https",
        "wsgi.input": io.BytesIO(payload),
        "wsgi.errors": io.BytesIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(payload)),
        "REMOTE_ADDR": remote_addr,
    }
    for key, value in (headers or {}).items():
        environ["HTTP_" + key.upper().replace("-", "_")] = value

    captured = {}

    def start_response(status, response_headers, exc_info=None):
        captured["status"] = int(status.split(" ", 1)[0])
        captured["headers"] = dict(response_headers)

    list(appmod.app(environ, start_response))
    return captured["status"], captured["headers"]


def run_burst(n=35, **kwargs):
    return [call(**kwargs)[0] for _ in range(n)]


# ── The bypass itself ──────────────────────────────────────────────────────

def test_rotating_forwarded_header_no_longer_bypasses_the_limit():
    codes = run_burst(
        remote_addr="10.0.0.7",  # proxied, as on Render
        headers={"X-Forwarded-For": f"8.8.8.1, {CLIENT}"},
    )
    assert codes.count(200) == config.RATE_LIMIT_REQUESTS
    assert 429 in codes


def test_each_request_may_carry_a_different_forged_prefix():
    codes = []
    for i in range(1, 36):
        codes.append(call(remote_addr="10.0.0.7",
                          headers={"X-Forwarded-For": f"8.8.8.{i}, {CLIENT}"})[0])
    assert codes.count(200) == config.RATE_LIMIT_REQUESTS, \
        "rotating the forged prefix bought extra requests"


def test_direct_caller_cannot_invent_buckets():
    # Public peer address: nothing is in front of us, so the header is fiction.
    codes = []
    for i in range(1, 36):
        codes.append(call(remote_addr=CLIENT,
                          headers={"X-Forwarded-For": f"8.8.8.{i}"})[0])
    assert codes.count(200) == config.RATE_LIMIT_REQUESTS


def test_cloudflare_header_wins_over_forged_chain():
    codes = []
    for i in range(1, 36):
        codes.append(call(remote_addr="10.0.0.7",
                          headers={"CF-RAY": "abc", "CF-Connecting-IP": CLIENT,
                                   "X-Forwarded-For": f"8.8.8.{i}"})[0])
    assert codes.count(200) == config.RATE_LIMIT_REQUESTS


# ── and the limit must still be per-client ─────────────────────────────────

def test_genuinely_different_clients_are_not_punished_for_each_other():
    codes = []
    for i in range(1, 36):
        codes.append(call(remote_addr="10.0.0.7",
                          headers={"X-Forwarded-For": f"104.18.1.1, 8.8.8.{i}"})[0])
    assert 429 not in codes, "35 separate clients were limited as one"


# ── request size ───────────────────────────────────────────────────────────

def test_oversize_body_is_refused():
    status, _ = call(body={"domain": "a" * (config.MAX_BODY_BYTES + 1000)},
                     remote_addr=CLIENT)
    assert status == 413


def test_normal_body_is_accepted():
    status, _ = call(remote_addr=CLIENT)
    assert status == 200


# ── headers ────────────────────────────────────────────────────────────────

def test_security_headers_present_on_every_response():
    _, headers = call(remote_addr=CLIENT)
    assert headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "max-age=" in headers["Strict-Transport-Security"]
    assert headers["X-Robots-Tag"] == "noindex, nofollow"


def test_unlisted_origin_gets_no_cors_grant():
    _, headers = call(remote_addr=CLIENT, headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in headers


def test_listed_origin_is_granted():
    _, headers = call(remote_addr=CLIENT, headers={"Origin": "https://myrecon.xyz"})
    assert headers["Access-Control-Allow-Origin"] == "https://myrecon.xyz"


# ── cross-site form posts ──────────────────────────────────────────────────

def call_raw(content_type, body=b'{"domain":"example.com"}', remote_addr=CLIENT):
    environ = {
        "REQUEST_METHOD": "POST", "PATH_INFO": "/api/dns",
        "SERVER_NAME": "testserver", "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https", "wsgi.input": io.BytesIO(body),
        "wsgi.errors": io.BytesIO(), "wsgi.multithread": False,
        "wsgi.multiprocess": False, "wsgi.run_once": False,
        "CONTENT_LENGTH": str(len(body)), "REMOTE_ADDR": remote_addr,
    }
    if content_type is not None:
        environ["CONTENT_TYPE"] = content_type
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = int(status.split(" ", 1)[0])

    list(appmod.app(environ, start_response))
    return captured["status"]


@pytest.mark.parametrize("content_type", [
    "text/plain",                          # <form enctype="text/plain">
    "application/x-www-form-urlencoded",   # the default form encoding
    "multipart/form-data",                 # file-upload form encoding
    None,                                  # no header at all
])
def test_simple_cross_site_form_posts_are_refused(content_type):
    # These are the content types a browser will send cross-origin with no
    # preflight. Refusing them forces a preflight, which CORS can then gate.
    assert call_raw(content_type) == 415


def test_real_json_requests_still_work():
    assert call_raw("application/json") == 200
    assert call_raw("application/json; charset=utf-8") == 200
