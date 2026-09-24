"""
Regression tests for client-IP resolution.

These exist because the rate limiter was measurably bypassable: 34 requests to
production carrying a rotating `X-Forwarded-For` all returned 200, while the
same 34 without the header returned 30x 200 then 429. The limiter was fine; the
key it bucketed on was attacker-supplied. Every case below is a way that can
come back.

Note on addresses: 203.0.113.0/24 and friends are documentation ranges that
Python's `ipaddress` classifies as private, so they cannot be used as stand-ins
for a public client here. Real routable addresses are used deliberately.

Run:  python -m pytest tests/ -q      (from backend/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.clientip import resolve  # noqa: E402

CLIENT = "93.184.216.34"   # the real caller
FAKE = "104.18.32.47"      # what an attacker types into the header


class Headers(dict):
    """Minimal case-insensitive stand-in for Flask's request.headers."""

    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


def test_spoofed_xff_loses_to_cloudflare_header():
    h = Headers({"CF-RAY": "abc", "CF-Connecting-IP": CLIENT,
                 "X-Forwarded-For": f"{FAKE}, {CLIENT}"})
    assert resolve(h, "10.0.0.1") == CLIENT


def test_spoofed_xff_loses_to_rightmost_entry():
    h = Headers({"X-Forwarded-For": f"{FAKE}, {CLIENT}"})
    assert resolve(h, "10.0.0.1") == CLIENT


def test_flooding_the_chain_does_not_help():
    h = Headers({"X-Forwarded-For": f"1.1.1.1, 2.2.2.2, {FAKE}, {CLIENT}"})
    assert resolve(h, "10.0.0.1") == CLIENT


def test_internal_hop_appended_after_client_is_skipped():
    h = Headers({"X-Forwarded-For": f"{FAKE}, {CLIENT}, 10.2.3.4"})
    assert resolve(h, "10.0.0.1") == CLIENT


def test_cloudflare_header_alone_is_not_self_authorising():
    # Without CF-RAY the request did not come through the edge, so
    # CF-Connecting-IP is just a header the caller typed.
    h = Headers({"CF-Connecting-IP": FAKE})
    assert resolve(h, CLIENT) == CLIENT


def test_private_cloudflare_value_falls_through():
    h = Headers({"CF-RAY": "x", "CF-Connecting-IP": "10.1.1.1",
                 "X-Forwarded-For": f"{FAKE}, {CLIENT}"})
    assert resolve(h, "10.0.0.1") == CLIENT


def test_all_private_chain_falls_back_to_socket():
    h = Headers({"X-Forwarded-For": "10.0.0.5, 192.168.1.1"})
    assert resolve(h, CLIENT) == CLIENT


def test_garbage_chain_falls_back_to_socket():
    h = Headers({"X-Forwarded-For": "not-an-ip, <script>alert(1)</script>"})
    assert resolve(h, CLIENT) == CLIENT


def test_ports_are_stripped():
    assert resolve(Headers({"X-Forwarded-For": f"{FAKE}, {CLIENT}:51234"}), "10.0.0.1") == CLIENT
    assert resolve(
        Headers({"X-Forwarded-For": f"{FAKE}, [2606:2800:220:1::1]:443"}), "10.0.0.1"
    ) == "2606:2800:220:1::1"


def test_trusted_proxy_depth_drops_extra_hops():
    h = Headers({"X-Forwarded-For": f"{FAKE}, {CLIENT}, 104.18.9.9"})
    assert resolve(h, "10.0.0.1", trusted_proxy_depth=1) == CLIENT


def test_depth_beyond_chain_length_is_safe():
    h = Headers({"X-Forwarded-For": FAKE})
    assert resolve(h, CLIENT, trusted_proxy_depth=5) == CLIENT


def test_nothing_resolvable_buckets_together():
    assert resolve(Headers({}), "") == "unknown"


# ── XFF is only meaningful when something in front of us wrote it ──────────

def test_direct_connection_ignores_forwarded_header_entirely():
    # Public socket peer means the caller dialled us directly. Nothing appended
    # to X-Forwarded-For, so every entry in it — either end — is theirs.
    h = Headers({"X-Forwarded-For": FAKE})
    assert resolve(h, CLIENT) == CLIENT


def test_direct_connection_cannot_be_split_into_many_buckets():
    seen = {resolve(Headers({"X-Forwarded-For": f"8.8.8.{i}"}), CLIENT) for i in range(1, 40)}
    assert seen == {CLIENT}, "a direct caller rotated the header into new buckets"


def test_private_socket_peer_means_a_proxy_wrote_the_header():
    # How Render reaches the app: connection handed over a private network.
    h = Headers({"X-Forwarded-For": f"{FAKE}, {CLIENT}"})
    assert resolve(h, "10.0.0.7") == CLIENT


def test_configured_depth_also_enables_trust():
    h = Headers({"X-Forwarded-For": f"{FAKE}, {CLIENT}, 104.18.9.9"})
    assert resolve(h, CLIENT, trusted_proxy_depth=1) == CLIENT


def test_missing_peer_address_does_not_collapse_everyone_into_one_bucket():
    # Some WSGI servers leave REMOTE_ADDR empty. Returning "unknown" for all of
    # them would be a single shared limit for every visitor, so the forwarded
    # chain is used instead.
    seen = {resolve(Headers({"X-Forwarded-For": f"104.18.1.1, 8.8.8.{i}"}), "")
            for i in range(1, 10)}
    assert len(seen) == 9, f"callers collapsed into {seen}"


def test_no_identity_at_all_still_buckets_together():
    assert resolve(Headers({}), "") == "unknown"
