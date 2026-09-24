"""
Spoof-resistant client IP resolution.

The rate limiter is only as good as the key it buckets on, and the obvious key
— the first entry of ``X-Forwarded-For`` — is supplied by the client. Proxies
*append* to that header, so the leftmost entry is whatever the caller typed.
Trusting it let anyone rotate a header and bypass the limit entirely:

    for i in 1..34: curl -H "X-Forwarded-For: 203.0.113.$i" .../api/dns
    -> 34x 200, zero 429     (measured against production before this change)

The same run without the header produced 30x 200 then 429, i.e. the limiter
worked perfectly and was simply being addressed on a field the attacker owned.

What is actually trustworthy is the *rightmost* end of the chain, because every
hop can only append. So the resolution order here is:

1. ``CF-Connecting-IP`` — Cloudflare fronts this deployment and *overwrites*
   this header rather than appending, so a client-supplied value never
   survives. Only consulted when the request really did arrive through the
   edge, which `_via_trusted_edge` checks.
2. The rightmost public address in ``X-Forwarded-For``, skipping the private
   and reserved hops that infrastructure adds behind the edge.
3. ``remote_addr``, the socket peer, which no header can influence.

`TRUSTED_PROXY_DEPTH` exists for deployments with extra appending hops in front
of the app: it drops that many entries off the right of the chain before
looking for the client. The default of 0 is correct for Render and for any
single-edge setup.
"""

import ipaddress
from typing import Iterable, Optional

# Cloudflare sets `CF-RAY` on everything it proxies and strips any inbound copy,
# so it is the marker that a request genuinely traversed the edge. It has to be
# a *different* header from the one being trusted: accepting `CF-Connecting-IP`
# as its own proof of origin would let a caller authorise their own spoof by
# sending that single header.
_EDGE_MARKER = "CF-RAY"


def _public(value: str) -> Optional[str]:
    """Return `value` if it parses as a routable public address, else None."""
    candidate = value.strip()
    if not candidate:
        return None
    # IPv6 arrives bracketed and sometimes with a port: [2001:db8::1]:443
    if candidate.startswith("["):
        candidate = candidate[1:].split("]", 1)[0]
    elif candidate.count(":") == 1:
        candidate = candidate.split(":", 1)[0]  # IPv4:port
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_reserved
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_unspecified
    ):
        return None
    return str(parsed)


def _via_trusted_edge(headers) -> bool:
    return bool(headers.get(_EDGE_MARKER))


def _behind_a_proxy(headers, remote_addr: str, trusted_proxy_depth: int) -> bool:
    """
    Whether `X-Forwarded-For` was written by infrastructure rather than by the caller.

    This check is the whole point. Reading the rightmost entry is only safer
    than reading the leftmost if something actually appended to the header; with
    nothing in front of the app, both ends are the caller's and "rightmost" is
    just a longer way of trusting them.

    Three signals, any one of which is sufficient:

    * `CF-RAY` — the request came through Cloudflare, which appends.
    * a configured `TRUSTED_PROXY_DEPTH` — the operator says hops exist.
    * a non-public socket peer — we are being handed connections over a private
      network, which is what being behind a load balancer looks like. Render
      reaches the app this way. If the peer address is public the client dialled
      us directly, and everything in the header is theirs.
    """
    if _via_trusted_edge(headers) or trusted_proxy_depth > 0:
        return True
    # An absent peer address counts as "not a direct connection" too. Some WSGI
    # servers simply do not populate REMOTE_ADDR, and treating that as a direct
    # call sends every such request to the same "unknown" bucket — which is not
    # a stricter limit, it is one shared limit for the whole internet, and the
    # first burst locks everybody out. With no socket identity to use, the
    # rightmost forwarded entry is the best evidence available.
    return _public(remote_addr or "") is None


def resolve(headers, remote_addr: str, trusted_proxy_depth: int = 0) -> str:
    """
    Best available identity for the caller, preferring fields a client cannot set.

    `headers` is any mapping with a case-insensitive `.get` (Flask's
    `request.headers` qualifies). Returns "unknown" when nothing resolves, which
    buckets unidentifiable callers together rather than letting them through.
    """
    if not _behind_a_proxy(headers, remote_addr, trusted_proxy_depth):
        # Direct connection: the socket peer is the only honest answer.
        return _public(remote_addr or "") or (remote_addr or "unknown")

    if _via_trusted_edge(headers):
        edge_ip = _public(headers.get("CF-Connecting-IP", "") or "")
        if edge_ip:
            return edge_ip

    chain: Iterable[str] = [
        part for part in (headers.get("X-Forwarded-For", "") or "").split(",") if part.strip()
    ]
    hops = list(chain)
    if trusted_proxy_depth > 0:
        hops = hops[: -trusted_proxy_depth] or []
    # Right to left: the far right was written by the hop closest to us, which
    # is the only part of this header we did not let the caller author.
    for hop in reversed(hops):
        found = _public(hop)
        if found:
            return found

    return _public(remote_addr or "") or (remote_addr or "unknown")


def forwarded_hop_count(headers) -> int:
    """How many entries the X-Forwarded-For chain carries. Diagnostics only."""
    return len([p for p in (headers.get("X-Forwarded-For", "") or "").split(",") if p.strip()])
