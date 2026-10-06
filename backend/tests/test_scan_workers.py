"""Worker presence and private-operator API regressions."""
import secrets
import threading

import pytest

import app as api
import config
from core import plans, scan_jobs as jobs, scan_workers as workers, store as storage
from services import scan_engine, scan_job_runner


@pytest.fixture
def setup(monkeypatch):
    memory = storage._MemoryStore()
    monkeypatch.setattr(storage, "store", memory)
    monkeypatch.setattr(plans, "store", memory)
    monkeypatch.setattr(config, "IS_PRODUCTION", False)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", True)
    monkeypatch.setattr(config, "SCAN_OFFLOAD_ENABLED", True)
    monkeypatch.setattr(config, "SCAN_WORKER_TOKEN", secrets.token_hex(32))
    monkeypatch.setattr(config, "SCAN_WORKER_STATUS_TOKEN", secrets.token_hex(32))
    monkeypatch.setattr(config, "SCAN_WORKER_OPERATOR_EMAIL", "owner@example.test")
    monkeypatch.setattr(config, "SCAN_WORKER_LAUNCHER_URL", "https://script.google.com/macros/s/private/exec")
    monkeypatch.setattr(config, "SCAN_WORKER_FRESH_SECONDS", 30)
    monkeypatch.setattr(config, "SCAN_WORKER_OFFLINE_SECONDS", 180)
    monkeypatch.setattr(config, "SCAN_WORKER_RETENTION_SECONDS", 3600)
    monkeypatch.setattr(config, "SCAN_JOB_LIMIT", 2)
    monkeypatch.setattr(config, "SCAN_LEASE_SECONDS", 30)
    monkeypatch.setattr(config, "SCAN_WORKER_WAIT_SECONDS", 20)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "CACHE_ENABLED", False)
    monkeypatch.setattr(scan_engine, "catalogue", lambda *a, **k: [])
    monkeypatch.setattr(scan_engine, "fingerprint", lambda *a, **k: "version-one")
    monkeypatch.setattr(scan_job_runner, "ensure_started", lambda: None)
    monkeypatch.setattr(api, "_full_slots", threading.BoundedSemaphore(1))
    return memory, api.create_app().test_client()


def _auth():
    return {"Authorization": "Bearer " + config.SCAN_WORKER_TOKEN}


def _claim(client, worker_id="worker-presence-123456", label="Worker 01"):
    return client.post("/api/scan-worker/claim", json={
        "worker_id": worker_id,
        "worker_label": label,
        "catalogues": {"full": "version-one"},
        "protocol": scan_engine.PROTOCOL,
    }, headers=_auth())


def _queue():
    job_id = "a" * 32
    jobs.reserve(job_id, "fixture", "full", False, "owner", "u")
    return jobs.admit(job_id, None)


def test_idle_claim_records_liveness_with_a_stable_label(setup):
    _, client = setup
    response = _claim(client)
    assert response.status_code == 200
    assert response.json["job"] is None
    status = workers.status()
    assert status["workers"] == [{
        "label": "Worker 01", "state": "idle", "available": True,
        "last_seen_at": status["workers"][0]["last_seen_at"], "age_seconds": 0,
        "duplicate": False,
    }]


def test_worker_status_tracks_busy_recovery_stop_and_staleness(setup):
    memory, client = setup
    _queue()
    assigned = _claim(client).json["job"]
    assert workers.status()["workers"][0]["state"] == "busy"

    response = client.post("/api/scan-worker/heartbeat", json={
        "job_id": assigned["id"], "lease_token": assigned["token"],
    }, headers=_auth())
    assert response.status_code == 200
    assert workers.status()["workers"][0]["state"] == "busy"

    response = client.post("/api/scan-worker/release", json={
        "job_id": assigned["id"], "lease_token": assigned["token"],
    }, headers=_auth())
    assert response.status_code == 200
    assert workers.status()["workers"][0]["state"] == "recovering"
    # Render takes the released job, so the worker's next poll is truly idle.
    assert jobs.claim("render") is not None
    assert _claim(client).json["job"] is None
    assert workers.status()["workers"][0]["state"] == "idle"

    records = memory.get(workers.ROOT)
    records["worker-presence-123456"]["last_seen_at"] -= 200
    memory.set(workers.ROOT, records)
    assert workers.status()["workers"][0]["state"] == "offline"

    response = client.post("/api/scan-worker/stopped", json={
        "worker_id": "worker-presence-123456",
    }, headers=_auth())
    assert response.status_code == 200
    assert workers.status()["workers"][0]["state"] == "stopped"


def test_status_token_is_distinct_and_never_returns_job_or_instance_data(setup):
    _, client = setup
    _claim(client)
    assert client.get("/api/operator/scan-workers").status_code == 401
    assert client.get("/api/operator/scan-workers", headers=_auth()).status_code == 401
    response = client.get("/api/operator/scan-workers", headers={
        "Authorization": "Bearer " + config.SCAN_WORKER_STATUS_TOKEN,
    })
    assert response.status_code == 200
    worker = response.json["workers"][0]
    assert set(worker) == {"label", "state", "available", "last_seen_at", "age_seconds", "duplicate"}
    assert "job" not in response.json
    assert config.SCAN_WORKER_TOKEN not in response.get_data(as_text=True)


def test_owner_console_requires_the_configured_firebase_email(setup, monkeypatch):
    _, client = setup
    _claim(client)
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "other", "email": "other@example.test"})
    assert client.get("/api/operator/worker-console").status_code == 403
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "owner", "email": "owner@example.test"})
    response = client.get("/api/operator/worker-console")
    assert response.status_code == 200
    assert response.json["launcher_url"] == config.SCAN_WORKER_LAUNCHER_URL
    assert "email" not in response.json


def test_presence_write_failure_cannot_abandon_a_claim(setup, monkeypatch):
    _, client = setup
    _queue()
    monkeypatch.setattr(workers, "seen_claim", lambda *args: (_ for _ in ()).throw(OSError("unavailable")))
    response = _claim(client)
    assert response.status_code == 200
    assert response.json["job"]["id"] == "a" * 32


def test_prune_removes_long_stale_records(setup):
    memory, client = setup
    _claim(client)
    records = memory.get(workers.ROOT)
    records["worker-presence-123456"]["last_seen_at"] -= 3601
    memory.set(workers.ROOT, records)
    workers.prune()
    assert memory.get(workers.ROOT) == {}
