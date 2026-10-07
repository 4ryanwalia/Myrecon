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
import time
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

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


def _refuse_internal(url: str) -> list[str]:
    """Raise unless `url` is http(s) pointing at a public address."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise BlockedRequest(f"scheme not allowed: {parts.scheme or '(none)'}")
    host = parts.hostname
    if not host:
        raise BlockedRequest("no host in URL")

    if parts.username is not None or parts.password is not None:
        raise BlockedRequest("URL credentials are not allowed")
    addresses = _addresses_for(host)
    if not addresses:
        raise BlockedRequest("no destination addresses")
    for address in addresses:
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
    return addresses


class _PinnedAdapter(HTTPAdapter):
    """Keep the original HTTP/TLS hostname, but connect only to a checked IP."""

    def __init__(self, address: str):
        class PinnedSocket:
            def _new_conn(self):
                sock = socket.create_connection(
                    (address, self.port), timeout=self.timeout,
                    source_address=self.source_address,
                )
                try:
                    for option in self.socket_options or []:
                        sock.setsockopt(*option)
                    return sock
                except BaseException:
                    sock.close()
                    raise

        class PinnedHTTP(PinnedSocket, HTTPConnection):
            pass

        class PinnedHTTPS(PinnedSocket, HTTPSConnection):
            pass

        class HTTPPool(HTTPConnectionPool):
            ConnectionCls = PinnedHTTP

        class HTTPSPool(HTTPSConnectionPool):
            ConnectionCls = PinnedHTTPS

        self._pool_classes = {"http": HTTPPool, "https": HTTPSPool}
        super().__init__(max_retries=0)

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        # Copy rather than change urllib3's shared class mapping.
        self.poolmanager.pool_classes_by_scheme = dict(self._pool_classes)


def safe_get(url: str, *, allowed_hosts=None, redirect_limit=_MAX_REDIRECTS, **kwargs) -> requests.Response:
    """
    `requests.get` for URLs we did not choose.

    Redirects are followed manually so every hop is checked; `allow_redirects`
    in kwargs is ignored for that reason. Raises `BlockedRequest` when a hop
    points anywhere internal, and lets `requests` exceptions through unchanged.
    `allowed_hosts` narrows destinations; `redirect_limit=0` refuses redirects.
    """
    kwargs.pop("allow_redirects", None)
    if type(redirect_limit) is not int or not 0 <= redirect_limit <= _MAX_REDIRECTS:
        raise BlockedRequest("invalid redirect limit")
    streaming = kwargs.pop("stream", False)
    deadline = time.monotonic() + 20
    if kwargs.get("verify") is False or kwargs.get("proxies"):
        raise BlockedRequest("unverified TLS and proxy overrides are not allowed")
    current = url

    for _ in range(redirect_limit + 1):
        # Optional adapters can narrow the destination policy further. Check
        # every hop before DNS or connection, not only the final response URL.
        if allowed_hosts is not None and urlsplit(current).hostname not in allowed_hosts:
            raise BlockedRequest("destination is outside the allowed hosts")
        addresses = _refuse_internal(current)
        session = requests.Session()
        session.trust_env = False  # no environment proxies, cookies or .netrc
        adapter = _PinnedAdapter(addresses[0])
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        try:
            resp = session.get(current, allow_redirects=False, stream=True, **kwargs)
        except BaseException:
            session.close()
            raise
        original_close = resp.close
        def close_response(close=original_close, owner=session):
            try:
                close()
            finally:
                owner.close()
        resp.close = close_response
        location = resp.headers.get("Location")
        if resp.status_code not in (301, 302, 303, 307, 308) or not location:
            if not streaming:
                try:
                    chunks, size = [], 0
                    for chunk in resp.iter_content(16_384):
                        size += len(chunk)
                        if size > 2_000_000 or time.monotonic() > deadline:
                            raise BlockedRequest("upstream response limit exceeded")
                        chunks.append(chunk)
                    resp._content = b"".join(chunks)
                    resp._content_consumed = True
                finally:
                    resp.close()
            return resp
        current = requests.compat.urljoin(current, location)
        resp.close()
        # Query parameters belong only to the initial request, not redirects.
        kwargs.pop("params", None)

    raise BlockedRequest("too many redirects")
