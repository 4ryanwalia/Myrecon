"""Large catalogues must finish without unbounded submissions or orphan work."""
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parents[1]))
import config
import modules.sweep as sweep_module
import services.search as search
from modules.sweep import EXTENDED, FOUND, UNKNOWN, Sweep


def test_entire_extended_catalogue_with_bounded_submission(monkeypatch):
    sweep = Sweep("fixture", concurrency=8, deadline_seconds=30)
    lock = threading.Lock()
    submitted = finished = peak = 0
    visited = []
    original = sweep_module.ThreadPoolExecutor

    class TrackedExecutor(original):
        def submit(self, fn, *args, **kwargs):
            nonlocal submitted, peak
            with lock:
                submitted += 1
                peak = max(peak, submitted - finished)
            return super().submit(fn, *args, **kwargs)

    def probe(p):
        nonlocal finished
        time.sleep(0.001)
        with lock:
            visited.append(p["name"])
            finished += 1
        return sweep._hit(p, FOUND, sweep._url_for(p, "fixture"), 200, "high", "api_user")

    monkeypatch.setattr(sweep_module, "ThreadPoolExecutor", TrackedExecutor)
    monkeypatch.setattr(sweep, "probe", probe)
    hits, coverage = sweep.run(platforms=EXTENDED)
    assert len(hits) == len(EXTENDED) == len(visited)
    assert sorted(visited) == sorted(p["name"] for p in EXTENDED)
    assert peak <= 8
    assert coverage["found"] == len(EXTENDED)
    assert coverage["unchecked"] == 0


def test_expired_budget_records_every_omission_as_unknown(monkeypatch):
    sweep = Sweep("fixture", concurrency=2, deadline_seconds=-1)
    monkeypatch.setattr(sweep, "probe", lambda p: pytest.fail("Expired scan started a probe"))
    hits, coverage = sweep.run(platforms=EXTENDED)
    assert len(hits) == coverage["unchecked"] == len(EXTENDED)
    assert all(h["verdict"] == UNKNOWN and h["reason_code"] == "out_of_time" for h in hits)


def test_cancelled_scan_does_not_start_more_work(monkeypatch):
    sweep = Sweep("fixture", concurrency=2)
    calls = []

    def probe(p):
        calls.append(p["name"])
        sweep.stop()
        return sweep._hit(p, FOUND, sweep._url_for(p, "fixture"), 200, "high", "api_user")

    monkeypatch.setattr(sweep, "probe", probe)
    hits, coverage = sweep.run(platforms=EXTENDED)
    assert 1 <= len(calls) <= 2
    assert len(hits) == len(EXTENDED)
    assert coverage["unchecked"] == len(EXTENDED) - len(calls)


def test_stopped_scan_cannot_start_followup_http_requests(monkeypatch):
    sweep = Sweep("fixture")
    sweep.stop()
    monkeypatch.setattr(sweep.session, "get", lambda *a, **k: pytest.fail("HTTP after stop"))
    with pytest.raises(requests.Timeout):
        sweep._html_get(EXTENDED[0], "https://example.com/fixture")
    # API fallback must also avoid issuing a request after cancellation.
    assert sweep._probe_api({**EXTENDED[0], "api": "https://example.com/{username}"}, "fixture") is None
    sweep.session.close()


def test_stream_close_stops_worker_even_with_full_event_queue(monkeypatch):
    finished = threading.Event()
    stopped = []

    def run(username, emit, extended=False, stop_event=None):
        try:
            emit({"type": "progress", "percent": 2})
            for i in range(200):
                emit({"type": "progress", "percent": i})
            stopped.append(stop_event.is_set())
            return {"status": "ok"}
        finally:
            finished.set()

    monkeypatch.setattr(search, "_run_full", run)
    events = search.stream_username("fixture", scope="extended")
    assert next(events)["type"] == "progress"
    events.close()
    assert finished.is_set()
    assert stopped == [True]


def test_sweep_budget_exhaustion_marks_response_partial(monkeypatch):
    options = {}

    class FakeSweep:
        def __init__(self, username, **kwargs):
            options.update(kwargs)

        def run(self, on_result=None, platforms=None):
            assert platforms is EXTENDED
            return [], {"total": len(EXTENDED), "unchecked": 3}

    monkeypatch.setattr(sweep_module, "Sweep", FakeSweep)
    monkeypatch.setattr(search, "_enrich_profiles", lambda *a: None)
    monkeypatch.setattr(search, "_code_exposure", lambda *a: [])
    result = search._run_full("fixture", extended=True)
    assert options["concurrency"] == config.SWEEP_CONCURRENCY
    assert options["deadline_seconds"] == config.EXTENDED_SCAN_DEADLINE_SECONDS
    assert result["partial"] is True
    assert result["errors"][0]["code"] == "timeout"
