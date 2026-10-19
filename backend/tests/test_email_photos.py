import socket

import pytest

from modules import email_photos as photos


URL = "https://avatars.githubusercontent.com/u/42?v=4"
PNG = b"\x89PNG\r\n\x1a\n" + b"fixture-raster-body"


class Reply:
    def __init__(self, body=PNG, status=200, headers=None):
        self.status = status
        self.headers = {"Content-Type": "image/png", **(headers or {})}
        self.body = body
        self.cursor = 0

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read(self, size):
        block = self.body[self.cursor:self.cursor + size]
        self.cursor += len(block)
        return block


class Connection:
    sock = None
    closed = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    photos._cache.clear()
    monkeypatch.setattr(photos, "_cache_bytes", 0)
    monkeypatch.setattr(photos.socket, "getaddrinfo", lambda *args, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    ])


def transport(monkeypatch, *replies):
    sequence, calls, connections = iter(replies), [], []

    def open_image(host, target, address, timeout):
        calls.append((host, target, address, timeout))
        connection = Connection()
        connections.append(connection)
        return connection, next(sequence)

    monkeypatch.setattr(photos, "_open_image", open_image)
    return calls, connections


def test_public_image_is_pinned_cached_and_connection_closed(monkeypatch):
    calls, connections = transport(monkeypatch, Reply())
    first = photos.fetch_public_photo(URL)
    assert first.body == PNG and first.content_type == "image/png"
    assert photos.fetch_public_photo(URL) is first
    assert calls == [("avatars.githubusercontent.com", "/u/42?v=4", "8.8.8.8", 5)]
    assert all(connection.closed for connection in connections)
    assert URL not in photos._cache


@pytest.mark.parametrize("url", [
    "http://avatars.githubusercontent.com/u/42", "https://127.0.0.1/photo",
    "https://avatars.githubusercontent.com.attacker.test/u/42",
    "https://attacker.test/image.png", "https://user:password@www.gravatar.com/avatar/fixture",
    "https://media.licdn.com:444/image", "https://media.licdn.com/image#fragment",
    "https://media.licdn.com/image\r\nHost: internal", "file:///etc/passwd",
    "https://media.licdn.com/\u2603",
])
def test_unsafe_url_never_uses_network(monkeypatch, url):
    calls, _ = transport(monkeypatch)
    with pytest.raises(photos.PhotoError):
        photos.fetch_public_photo(url)
    assert not calls


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "100.64.0.1",
    "::1", "fe80::1", "fc00::1", "::ffff:8.8.8.8",
])
def test_private_dns_answer_never_connects(monkeypatch, address):
    monkeypatch.setattr(photos.socket, "getaddrinfo", lambda *args, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
    ])
    calls, _ = transport(monkeypatch)
    with pytest.raises(photos.PhotoError, match="unsafe_photo_destination"):
        photos.fetch_public_photo(URL)
    assert not calls


def test_public_redirect_checks_destination_and_caches_original(monkeypatch):
    calls, connections = transport(monkeypatch,
        Reply(status=302, headers={"Location": "https://lh3.googleusercontent.com/a/fixture"}), Reply())
    assert photos.fetch_public_photo(URL).body == PNG
    assert [call[0] for call in calls] == ["avatars.githubusercontent.com", "lh3.googleusercontent.com"]
    assert all(connection.closed for connection in connections)
    photos.fetch_public_photo(URL)
    assert len(calls) == 2


def test_redirect_to_private_or_unknown_host_is_not_followed(monkeypatch):
    calls, connections = transport(monkeypatch,
        Reply(status=302, headers={"Location": "https://169.254.169.254/latest/meta-data"}))
    with pytest.raises(photos.PhotoError):
        photos.fetch_public_photo(URL)
    assert len(calls) == 1 and connections[0].closed


def test_redirect_new_dns_is_checked_before_second_request(monkeypatch):
    def dns(host, *args, **kwargs):
        address = "8.8.8.8" if host.startswith("avatars") else "10.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    monkeypatch.setattr(photos.socket, "getaddrinfo", dns)
    calls, _ = transport(monkeypatch,
        Reply(status=302, headers={"Location": "https://lh3.googleusercontent.com/a/fixture"}))
    with pytest.raises(photos.PhotoError, match="unsafe_photo_destination"):
        photos.fetch_public_photo(URL)
    assert len(calls) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_private_missing_and_throttled_images_are_not_cached(monkeypatch, status):
    _, connections = transport(monkeypatch, Reply(status=status))
    with pytest.raises(photos.PhotoError, match="photo_unavailable"):
        photos.fetch_public_photo(URL)
    assert not photos._cache and connections[0].closed


@pytest.mark.parametrize("body,headers", [
    (b"<html>Login</html>", {"Content-Type": "text/html"}),
    (b"<svg onload='alert(1)'/>", {"Content-Type": "image/svg+xml"}),
    (b"<html>Login</html>", {"Content-Type": "image/png"}),
    (PNG, {"Content-Type": "image/jpeg"}),
    (PNG, {"Content-Type": "image/png", "Content-Encoding": "gzip"}),
])
def test_non_raster_or_mislabelled_response_rejected(monkeypatch, body, headers):
    transport(monkeypatch, Reply(body, headers=headers))
    with pytest.raises(photos.PhotoError, match="unsupported_photo_type"):
        photos.fetch_public_photo(URL)
    assert not photos._cache


@pytest.mark.parametrize("declared", [False, True])
def test_response_size_is_bounded_with_or_without_length(monkeypatch, declared):
    monkeypatch.setattr(photos, "MAX_IMAGE_BYTES", 32)
    headers = {"Content-Length": "100"} if declared else {}
    transport(monkeypatch, Reply(PNG + b"X" * 100, headers=headers))
    with pytest.raises(photos.PhotoError, match="photo_too_large"):
        photos.fetch_public_photo(URL)
    assert not photos._cache


def test_cache_eviction_is_bounded(monkeypatch):
    monkeypatch.setattr(photos, "MAX_CACHE_ITEMS", 1)
    transport(monkeypatch, Reply(), Reply())
    photos.fetch_public_photo(URL)
    photos.fetch_public_photo("https://www.gravatar.com/avatar/fixture?d=404")
    assert len(photos._cache) == 1 and photos._cache_bytes == len(PNG)


def test_cache_expiry_fetches_fresh_data(monkeypatch):
    monkeypatch.setattr(photos, "CACHE_SECONDS", -1)
    calls, _ = transport(monkeypatch, Reply(), Reply())
    photos.fetch_public_photo(URL)
    photos.fetch_public_photo(URL)
    assert len(calls) == 2


def test_stalled_dns_does_not_connect_or_cache(monkeypatch):
    class Pending:
        def add_done_callback(self, fn):
            fn(self)
        def result(self, timeout):
            assert 0 < timeout <= photos.DNS_SECONDS
            raise photos.FutureTimeout()
    monkeypatch.setattr(photos._dns_workers, "submit", lambda *args, **kwargs: Pending())
    calls, _ = transport(monkeypatch)
    with pytest.raises(photos.PhotoError, match="photo_unavailable"):
        photos.fetch_public_photo(URL)
    assert not calls and not photos._cache


def test_route_public_image_corp_is_scoped_and_error_does_not_echo_url(monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod.config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(photos, "fetch_public_photo", lambda url: photos.Photo(PNG, "image/png"))
    client = appmod.create_app().test_client()
    response = client.get("/api/email/photo", query_string={"url": URL})
    assert response.status_code == 200 and response.data == PNG
    assert response.headers["Content-Type"] == "image/png"
    assert response.headers["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert response.headers["Cache-Control"] == "private, max-age=300"
    assert client.get("/api/health").headers["Cross-Origin-Resource-Policy"] == "same-site"
    def fail(url):
        raise photos.PhotoError("unsupported_photo_url", 400)
    monkeypatch.setattr(photos, "fetch_public_photo", fail)
    response = client.get("/api/email/photo", query_string={"url": "https://private.invalid/?token=fixture"})
    assert response.status_code == 400 and b"token" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_https_transport_uses_pinned_ip_and_original_tls_hostname(monkeypatch):
    calls = []
    class FakeContext:
        def wrap_socket(self, raw, server_hostname):
            calls.append(("tls", server_hostname))
            return raw
    class FakeSocket:
        def close(self):
            pass
    def create_socket(destination, timeout):
        calls.append(("connect", destination, timeout))
        return FakeSocket()
    monkeypatch.setattr(photos.socket, "create_connection", create_socket)
    connection = photos._PinnedHTTPSConnection("media.licdn.com", "8.8.8.8", 5)
    connection._context = FakeContext()
    connection.connect()
    assert calls == [("connect", ("8.8.8.8", 443), 5), ("tls", "media.licdn.com")]
