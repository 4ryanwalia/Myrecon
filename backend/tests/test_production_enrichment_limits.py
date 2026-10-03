import io
from unittest.mock import Mock

import pytest
import requests

from core import netguard
from modules import enrichment


def response(body=b"image", status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result.raw = io.BytesIO(body)
    result.encoding = "utf-8"
    result.close = Mock(wraps=result.close)
    return result


def test_avatar_stops_before_buffering_entire_upstream(monkeypatch):
    upstream = response()
    consumed = []
    def chunks(size):
        for _ in range(1000):
            consumed.append(1)
            yield b"x" * size
    upstream.iter_content = chunks
    monkeypatch.setattr(enrichment, "safe_get", lambda *a, **k: upstream)
    assert enrichment._download_image("https://images.example/avatar") == b""
    assert len(consumed) < 1000
    assert upstream.raw.closed


def test_small_avatar_is_returned_and_closed(monkeypatch):
    upstream = response(b"small image")
    monkeypatch.setattr(enrichment, "safe_get", lambda *a, **k: upstream)
    assert enrichment._download_image("https://images.example/avatar") == b"small image"
    upstream.close.assert_called_once()


def test_stream_deadline_rejects_slow_chunks(monkeypatch):
    upstream = response(b"image")
    ticks = iter([0, 9])
    monkeypatch.setattr(enrichment.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError):
        enrichment._bounded_body(upstream, 100, 6)


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_pinned_socket_keeps_tls_hostname_and_uses_checked_ip(monkeypatch, scheme):
    connected = []
    sock = Mock()
    monkeypatch.setattr(netguard.socket, "create_connection",
                        lambda destination, **kwargs: connected.append(destination) or sock)
    adapter = netguard._PinnedAdapter("93.184.216.34")
    pool = adapter.poolmanager.connection_from_url(f"{scheme}://attacker.example/image")
    connection = pool._new_conn()
    assert connection.host == "attacker.example"
    connection._new_conn()
    assert connected == [("93.184.216.34", 443 if scheme == "https" else 80)]
    adapter.close()


def test_mixed_dns_answers_fail_closed(monkeypatch):
    monkeypatch.setattr(netguard, "_addresses_for", lambda host: ["93.184.216.34", "127.0.0.1"])
    with pytest.raises(netguard.BlockedRequest):
        netguard._refuse_internal("https://attacker.example/image")


def test_redirect_is_revalidated_and_response_closed(monkeypatch):
    first = response(status=302, headers={"Location": "http://127.0.0.1/private"})
    session = Mock()
    session.get.return_value = first
    monkeypatch.setattr(netguard.requests, "Session", lambda: session)
    monkeypatch.setattr(netguard, "_addresses_for", lambda host: ["127.0.0.1"] if host == "127.0.0.1" else ["93.184.216.34"])
    with pytest.raises(netguard.BlockedRequest):
        netguard.safe_get("https://attacker.example/image", stream=True)
    assert first.raw.closed
    assert session.get.call_count == 1
    assert session.trust_env is False


def test_nonstreaming_response_is_bounded(monkeypatch):
    upstream = response(b"x" * 2_000_001)
    session = Mock()
    session.get.return_value = upstream
    monkeypatch.setattr(netguard.requests, "Session", lambda: session)
    monkeypatch.setattr(netguard, "_addresses_for", lambda host: ["93.184.216.34"])
    with pytest.raises(netguard.BlockedRequest):
        netguard.safe_get("https://attacker.example/image")
    assert upstream.raw.closed
