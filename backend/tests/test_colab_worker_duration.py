import pytest

from tools import colab_worker


class Clock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert 0 <= seconds <= 10
        self.now += seconds


class IdleHTTP:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def make_worker(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(colab_worker.time, 'monotonic', clock.monotonic)
    monkeypatch.setattr(colab_worker.time, 'sleep', clock.sleep)
    worker = colab_worker.Worker('https://myrecon.onrender.com', 'test-only-token-' * 3, http=IdleHTTP())
    return worker, clock


def test_default_worker_stays_available_for_ten_hours_and_retries_outage(monkeypatch):
    worker, clock = make_worker(monkeypatch)
    calls = []

    def claim(action, payload):
        assert action == 'claim'
        calls.append(clock.now)
        if len(calls) == 1:
            raise RuntimeError('Temporary network failure')
        return {'job': None}

    monkeypatch.setattr(worker, 'call', claim)
    worker.run()
    assert clock.now == 10 * 60 * 60
    assert max(calls) >= 9 * 60 * 60
    assert worker.http.closed
    assert worker.token == ''


def test_invalid_worker_configuration_stops_instead_of_retrying(monkeypatch):
    worker, clock = make_worker(monkeypatch)

    def refused(action, payload):
        raise ValueError('Worker configuration was refused')

    monkeypatch.setattr(worker, 'call', refused)
    with pytest.raises(ValueError):
        worker.run()
    assert clock.now == 0
    assert worker.http.closed
    assert worker.token == ''
