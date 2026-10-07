"""Bounded delivery of public profile images from known image CDNs.

The connection is pinned to a previously validated public IP while TLS still
verifies the original hostname. No cookies, credentials, environment proxies,
or authentication are forwarded. Login pages and private photos stay unavailable.
"""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
import hashlib
import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import urljoin, urlsplit, urlunsplit


MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_CACHE_ITEMS = 64
CACHE_SECONDS = 300
MAX_REDIRECTS = 3
READ_SECONDS = 5
DNS_SECONDS = 3
TOTAL_SECONDS = 12

ALLOWED_HOSTS = frozenset({
    "avatars.githubusercontent.com", "avatars0.githubusercontent.com",
    "avatars1.githubusercontent.com", "avatars2.githubusercontent.com",
    "avatars3.githubusercontent.com", "lh3.googleusercontent.com",
    "lh4.googleusercontent.com", "lh5.googleusercontent.com",
    "lh6.googleusercontent.com", "yt3.googleusercontent.com",
    "media.licdn.com", "media-exp1.licdn.com", "media-exp2.licdn.com",
    "media-exp3.licdn.com", "www.gravatar.com", "secure.gravatar.com",
    "gravatar.com", "0.gravatar.com", "1.gravatar.com", "2.gravatar.com",
})


class PhotoError(Exception):
    def __init__(self, code: str, status: int = 502):
        # Never place upstream URLs, tokens, or exception text in client errors.
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class Photo:
    body: bytes
    content_type: str


_cache = OrderedDict()
_cache_bytes = 0
_cache_lock = threading.Lock()
_dns_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="public-photo-dns")
_dns_slots = threading.BoundedSemaphore(2)


def validated_url(raw: str) -> tuple[str, str, str]:
    if not isinstance(raw, str) or not raw or len(raw) > 4096:
        raise PhotoError("invalid_photo_url", 400)
    if any(ord(char) < 33 or ord(char) == 127 for char in raw):
        raise PhotoError("invalid_photo_url", 400)
    if not raw.isascii():
        raise PhotoError("invalid_photo_url", 400)
    try:
        parts = urlsplit(raw)
        host = (parts.hostname or "").lower()
        if (parts.scheme != "https" or host not in ALLOWED_HOSTS or
                parts.username is not None or parts.password is not None or
                parts.port not in (None, 443) or parts.fragment):
            raise PhotoError("unsupported_photo_url", 400)
    except (TypeError, ValueError) as exc:
        raise PhotoError("invalid_photo_url", 400) from exc
    path = parts.path or "/"
    target = path + ("?" + parts.query if parts.query else "")
    return urlunsplit(("https", host, path, parts.query, "")), host, target


def _public_addresses(host: str, timeout: float = DNS_SECONDS) -> list[str]:
    # The OS resolver has no per-call timeout. Two bounded background slots keep
    # a stalled resolver from tying up a request worker or spawning more threads.
    if not _dns_slots.acquire(blocking=False):
        raise PhotoError("photo_unavailable")
    try:
        pending = _dns_workers.submit(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    except BaseException:
        _dns_slots.release()
        raise
    pending.add_done_callback(lambda future: _dns_slots.release())
    try:
        answers = pending.result(timeout=timeout)
        addresses = list(dict.fromkeys(item[4][0] for item in answers))
        if not addresses:
            raise PhotoError("photo_unavailable")
        # Reject mixed answers as well: never choose the safe half of a rebinding
        # or split-horizon response that also points at a private service.
        for value in addresses:
            address = ipaddress.ip_address(value)
            if not address.is_global or (address.version == 6 and address.ipv4_mapped):
                raise PhotoError("unsafe_photo_destination", 400)
        return addresses
    except (socket.gaierror, ValueError, FutureTimeout) as exc:
        raise PhotoError("photo_unavailable") from exc


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, port=443, timeout=timeout,
                         context=ssl.create_default_context())
        self._address = address

    def connect(self):
        raw_socket = socket.create_connection((self._address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except BaseException:
            raw_socket.close()
            raise


def _open_image(host: str, target: str, address: str, timeout: float):
    connection = _PinnedHTTPSConnection(host, address, timeout)
    try:
        connection.request("GET", target, headers={
            "User-Agent": "MyRecon-PublicPhoto/1.0",
            "Accept": "image/jpeg,image/png,image/webp,image/gif",
            "Accept-Encoding": "identity",
        })
        return connection, connection.getresponse()
    except BaseException:
        connection.close()
        raise


def _raster_type(body: bytes) -> str:
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if body.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _cache_get(key: str):
    global _cache_bytes
    now = time.monotonic()
    with _cache_lock:
        expired = [item for item, (expires, _) in _cache.items() if expires <= now]
        for item in expired:
            _cache_bytes -= len(_cache.pop(item)[1].body)
        entry = _cache.get(key)
        if entry:
            _cache.move_to_end(key)
            return entry[1]
    return None


def _cache_put(key: str, photo: Photo):
    global _cache_bytes
    with _cache_lock:
        old = _cache.pop(key, None)
        if old:
            _cache_bytes -= len(old[1].body)
        _cache[key] = (time.monotonic() + CACHE_SECONDS, photo)
        _cache_bytes += len(photo.body)
        while len(_cache) > MAX_CACHE_ITEMS or _cache_bytes > MAX_CACHE_BYTES:
            _cache_bytes -= len(_cache.popitem(last=False)[1][1].body)


def fetch_public_photo(url: str) -> Photo:
    normalized, _, _ = validated_url(url)
    key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cached = _cache_get(key)
    if cached:
        return cached
    deadline = time.monotonic() + TOTAL_SECONDS
    current = normalized
    try:
        for redirect in range(MAX_REDIRECTS + 1):
            _, host, target = validated_url(current)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PhotoError("photo_unavailable")
            addresses = _public_addresses(host, min(DNS_SECONDS, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PhotoError("photo_unavailable")
            connection, response = _open_image(host, target, addresses[0], min(READ_SECONDS, remaining))
            try:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location", "")
                    if redirect == MAX_REDIRECTS or not location:
                        raise PhotoError("photo_unavailable")
                    current = urljoin(current, location)
                    # Validate before the next DNS lookup or connection.
                    validated_url(current)
                    continue
                if response.status != 200:
                    raise PhotoError("photo_unavailable", 404 if response.status in (401, 403, 404) else 502)
                declared = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
                if declared not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
                    raise PhotoError("unsupported_photo_type", 415)
                if response.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
                    raise PhotoError("unsupported_photo_type", 415)
                length = response.getheader("Content-Length")
                if length:
                    try:
                        if int(length) < 0 or int(length) > MAX_IMAGE_BYTES:
                            raise PhotoError("photo_too_large", 413)
                    except ValueError as exc:
                        raise PhotoError("photo_unavailable") from exc
                chunks, size = [], 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise PhotoError("photo_unavailable")
                    if connection.sock:
                        connection.sock.settimeout(min(READ_SECONDS, remaining))
                    block = response.read(min(64 * 1024, MAX_IMAGE_BYTES - size + 1))
                    if not block:
                        break
                    chunks.append(block)
                    size += len(block)
                    if size > MAX_IMAGE_BYTES:
                        raise PhotoError("photo_too_large", 413)
                body = b"".join(chunks)
                if not body or _raster_type(body) != declared:
                    raise PhotoError("unsupported_photo_type", 415)
                photo = Photo(body, declared)
                _cache_put(key, photo)
                return photo
            finally:
                connection.close()
        raise PhotoError("photo_unavailable")
    except PhotoError:
        raise
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise PhotoError("photo_unavailable") from exc
