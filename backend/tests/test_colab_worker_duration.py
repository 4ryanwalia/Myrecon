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


def test_worker_reports_the_result_of_its_live_presence_check(monkeypatch, capsys):
    worker, _ = make_worker(monkeypatch)
    worker.note_presence({'presence_recorded': True})
    worker.note_presence({'presence_recorded': True})
    worker.note_presence({'presence_recorded': False})
    output = capsys.readouterr().out
    assert output.count('Live status confirmed') == 1
    assert 'could not save its live status' in output


def test_idle_worker_claims_within_two_seconds(monkeypatch):
    worker, clock = make_worker(monkeypatch)
    calls = []
    def claim(action, payload):
        if action == 'claim':
            calls.append(clock.now)
        return {'job': None}
    monkeypatch.setattr(worker, 'call', claim)
    worker.run(duration_minutes=1)
    assert len(calls) == 30
    assert max(b - a for a, b in zip(calls, calls[1:])) <= 2


def test_first_completed_batch_is_uploaded_before_enumeration_finishes(monkeypatch):
    worker, clock = make_worker(monkeypatch)
    actions = []
    monkeypatch.setattr(worker, 'call', lambda action, payload: actions.append(action) or {})
    def batches(*args):
        yield [{'platform': 'Example', 'exists': False}]
        assert actions == ['checkpoint']
        yield [{'platform': 'Second', 'exists': False}]
    monkeypatch.setattr(colab_worker.scan_engine, 'enumerate_batches', batches)
    worker.execute({'id': 'test', 'token': 'lease', 'username': 'fixture',
                    'scope': 'standard', 'deep': False,
                    'fingerprint': worker.catalogues['standard']})
    assert actions == ['checkpoint', 'checkpoint', 'complete']
