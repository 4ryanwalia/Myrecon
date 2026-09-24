"""
Outbound-request guard (SSRF).

Several modules fetch URLs that did not come from us: avatar and profile-picture
links carried in a platform's API response, and profile URLs harvested from
search results. Those are third-party strings, so "what host does this resolve
to" is not a question the caller gets to answer.

The address that matters is the cloud metadata service. On Render, as on every
major host, `http://169.254.169.254/` answers with instance credentials to
anything on the box that asks. A plain `requests.get(url)` on an attacker-chosen
URL is all it takes to read it, and a redirect to it works just as well, which
is why redirects are followed one hop at a time here instead of being handed to
`requests`.

`safe_get` enforces:
  * http/https only, no file://, gopher://, ftp://
  * every hop resolved to its IPs, with private, loopback, link-local,
    reserved, multicast and unspecified destinations refused
  * a redirect cap, since each hop is re-validated and a loop would otherwise
    spin

It is a drop-in for `requests.get` for the fetches described above. It is not
needed for calls to our own fixed third-party endpoints (archive.org, crt.sh,
rdap.org), where the host is a literal in our source.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

import requests

_ALLOWED_SCHEMES = ("http", "https")
_MAX_REDIRECTS = 3


class BlockedRequest(RuntimeError):
    """The destination is not one we are willing to fetch."""


def _addresses_for(host: str) -> list[str]:
    """Every address `host` resolves to. A literal IP resolves to itself."""
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    try:
        info = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError):
        raise BlockedRequest(f"cannot resolve host: {host}")
    return [entry[4][0] for entry in info]


def _refuse_internal(url: str) -> None:
    """Raise unless `url` is http(s) pointing at a public address."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise BlockedRequest(f"scheme not allowed: {parts.scheme or '(none)'}")
    host = parts.hostname
    if not host:
        raise BlockedRequest("no host in URL")

    for address in _addresses_for(host):
        # getaddrinfo hands back scoped IPv6 like fe80::1%eth0; the scope is
        # not part of the address and ip_address rejects it.
        parsed = ipaddress.ip_address(address.split("%")[0])
        # An IPv4 address tunnelled through IPv6 (::ffff:169.254.169.254) is
        # the same destination wearing a different hat, so unwrap before
        # judging it.
        if getattr(parsed, "ipv4_mapped", None):
            parsed = parsed.ipv4_mapped
        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_reserved
            or parsed.is_multicast
            or parsed.is_unspecified
        ):
            raise BlockedRequest(f"refusing internal address {parsed} for host {host}")


def safe_get(url: str, **kwargs) -> requests.Response:
    """
    `requests.get` for URLs we did not choose.

    Redirects are followed manually so every hop is checked; `allow_redirects`
    in kwargs is ignored for that reason. Raises `BlockedRequest` when a hop
    points anywhere internal, and lets `requests` exceptions through unchanged.
    """
    kwargs.pop("allow_redirects", None)
    current = url

    for _ in range(_MAX_REDIRECTS + 1):
        _refuse_internal(current)
        resp = requests.get(current, allow_redirects=False, **kwargs)
        if resp.status_code not in (301, 302, 303, 307, 308):
            return resp
        location = resp.headers.get("Location")
        if not location:
            return resp
        current = requests.compat.urljoin(current, location)

    raise BlockedRequest("too many redirects")
