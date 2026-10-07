"""Ownership, recovery, billing and wire-contract regressions. No provider calls."""
import copy
import hashlib
import hmac
import json
import secrets
import threading

import pytest

import app as api
import config
from core import history, plans, scan_jobs as jobs, store as storage
from services import scan_engine, scan_job_api, scan_job_runner, search

SPECS = [
    {"name": "GitHub", "url": "https://github.com/{username}", "category": "code", "expected": 200},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{username}", "category": "social", "expected": 200},
]


@pytest.fixture
def setup(monkeypatch):
    memory = storage._MemoryStore()
    monkeypatch.setattr(storage, "store", memory)
    monkeypatch.setattr(plans, "store", memory)
    monkeypatch.setattr(config, "IS_PRODUCTION", False)
    monkeypatch.setattr(config, "DEV_TEST_ACCOUNT", True)
    monkeypatch.setattr(config, "SCAN_OFFLOAD_ENABLED", True)
    monkeypatch.setattr(config, "SCAN_WORKER_TOKEN", secrets.token_hex(32))
    monkeypatch.setattr(config, "SCAN_JOB_LIMIT", 2)
    monkeypatch.setattr(config, "SCAN_LEASE_SECONDS", 30)
    monkeypatch.setattr(config, "SCAN_WORKER_WAIT_SECONDS", 20)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(config, "CACHE_ENABLED", False)
    monkeypatch.setattr(scan_engine, "catalogue", lambda *a, **k: SPECS)
    monkeypatch.setattr(scan_engine, "fingerprint", lambda *a, **k: "version-one")
    monkeypatch.setattr(scan_job_runner, "ensure_started", lambda: None)
    monkeypatch.setattr(api, "_full_slots", threading.BoundedSemaphore(1))
    client = api.create_app().test_client()
    return memory, client


def queued(job_id="a" * 32, scope="full", uid="u"):
    jobs.reserve(job_id, "fixture", scope, False, "owner", uid)
    return jobs.admit(job_id, None)


def versions():
    return {"standard": "version-one", "standard:deep": "version-one",
            "full": "version-one", "extended": "version-one"}


def test_admission_write_failure_preserves_committed_allowance(setup, monkeypatch):
    memory, _ = setup
    monkeypatch.setattr(scan_job_api, "_owner", lambda api: ("owner", "u"))
    monkeypatch.setattr(api, "_admit_scan", lambda scope, cached, job_id=None:
                        ("u", plans.consume_standard_scan("u", job_id=job_id)))
    original = jobs.admit
    monkeypatch.setattr(jobs, "admit", lambda *a: (_ for _ in ()).throw(OSError("database unavailable")))
    with api.app.test_request_context():
        with pytest.raises(OSError):
            scan_job_api._handle(api, {"username": "fixture", "request_id": "same-request-id-123"}, True)
    job = next(iter(memory.get(jobs.ROOT).values()))
    assert job["status"] == "admitting"
    assert plans.job_receipt("u", job["id"]) is not None
    job["created"] -= 61
    job["updated"] -= 61
    memory.set(jobs.ROOT, {job["id"]: job})
    monkeypatch.setattr(jobs, "admit", original)
    scan_job_runner.maintenance()
    assert jobs.get(job["id"])["status"] == "queued"
    assert plans.entitlements(memory.get("web/users/u"))["free_scans_left"] == 4


def test_pruned_request_cannot_reuse_old_charge(setup, monkeypatch):
    memory, _ = setup
    monkeypatch.setattr(scan_job_api, "_owner", lambda api: ("owner", "u"))
    raw = json.dumps(["owner", "same-request-id-123", "fixture", "standard", False])
    job_id = hmac.new(config.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    plans.consume_standard_scan("u", job_id=job_id)
    with api.app.test_request_context():
        response, status = scan_job_api._handle(api,
            {"username": "fixture", "request_id": "same-request-id-123"}, True)
    assert status == 410
    assert not memory.get(jobs.ROOT)


def hit(name="GitHub", verdict="found"):
    return {"platform": name, "url": "http://169.254.169.254/stolen", "verdict": verdict,
            "reason_code": "api_user" if verdict == "found" else "api_absent",
            "status_code": 200 if verdict == "found" else 404,
            "confidence": "high", "exists": verdict == "found"}


def complete_raw(job):
    jobs.checkpoint(job["id"], job["token"], 0, [hit(), hit("Reddit", "not_found")])
    return jobs.raw_done(job["id"], job["token"])


def test_colab_first_and_render_resumes_only_uncommitted_platforms(setup, monkeypatch):
    queued()
    assert jobs.claim("render") is None
    remote = jobs.claim("colab:worker", versions())
    jobs.checkpoint(remote["id"], remote["token"], 0, [hit()])
    expiry = jobs.get(remote["id"])["expires"]
    monkeypatch.setattr(jobs.time, "time", lambda: expiry + 1)
    fallback = jobs.claim("render")
    assert fallback["names"] == ["GitHub"]
    assert fallback["token"] != remote["token"]
    with pytest.raises(jobs.LostLease):
        jobs.checkpoint(remote["id"], remote["token"], 1, [hit("Reddit")])
    jobs.checkpoint(fallback["id"], fallback["token"], 0, [hit("Reddit", "not_found")])
    jobs.raw_done(fallback["id"], fallback["token"])
    assert [r["platform"] for r in jobs.rows(jobs.get(fallback["id"]))] == ["GitHub", "Reddit"]


def test_checkpoint_replays_are_idempotent_and_urls_are_canonical(setup):
    queued()
    job = jobs.claim("colab:worker", versions())
    jobs.checkpoint(job["id"], job["token"], 0, [hit()])
    jobs.checkpoint(job["id"], job["token"], 0, [hit()])
    assert jobs.get(job["id"])["checked"] == 1
    assert jobs.rows(jobs.get(job["id"]))[0]["url"] == "https://github.com/fixture"
    changed = hit(verdict="not_found")
    with pytest.raises(ValueError):
        jobs.checkpoint(job["id"], job["token"], 0, [changed])
    with pytest.raises(ValueError):
        jobs.checkpoint(job["id"], job["token"], 1, [hit()])
    with pytest.raises(ValueError):
        jobs.raw_done(job["id"], job["token"])


def test_corrupt_checkpoint_cannot_be_finalized(setup):
    memory, _ = setup
    queued()
    job = jobs.claim("colab:worker", versions())
    complete_raw(job)
    ref = jobs.get(job["id"])["refs"][0]
    memory.set(f"{jobs.DATA}/{job['id']}/chunks/{ref['path']}", [hit()])
    with pytest.raises(RuntimeError, match="corrupt"):
        jobs.rows(jobs.get(job["id"]))


def test_provider_999_and_firebase_null_removal_round_trip(setup, monkeypatch):
    memory, _ = setup
    original = memory.transaction

    def firebase_write(path, callback):
        def without_nulls(value):
            if isinstance(value, dict):
                return {k: without_nulls(v) for k, v in value.items() if v is not None}
            if isinstance(value, list):
                return [without_nulls(v) for v in value]
            return value
        return original(path, lambda old: without_nulls(callback(old)))

    monkeypatch.setattr(memory, "transaction", firebase_write)
    queued(scope="standard")
    job = jobs.claim("colab:worker", versions())
    rows = [{"platform": "GitHub", "exists": False, "status_code": 999,
             "match_score": None, "profile_pic_url": "https://[invalid"}]
    jobs.checkpoint(job["id"], job["token"], 0, rows)
    jobs.checkpoint(job["id"], job["token"], 0, rows)
    stored = jobs.rows(jobs.get(job["id"]))
    assert stored[0]["status_code"] == 999
    assert stored[0]["exists"] is False
    assert "match_score" not in stored[0]
    assert "profile_pic_url" not in stored[0]


def test_worker_claim_after_firebase_removes_empty_lists(setup):
    memory, client = setup
    job = queued()
    stored = memory.get(jobs.ROOT)
    for field in ("names", "refs", "charged", "guest_receipt_path"):
        stored[job["id"]].pop(field, None)
    memory.set(jobs.ROOT, stored)
    response = client.post('/api/scan-worker/claim', json={
        'worker_id': 'worker-fixture-123', 'catalogues': versions(),
        'protocol': scan_engine.PROTOCOL},
        headers={'Authorization': 'Bearer ' + config.SCAN_WORKER_TOKEN})
    assert response.status_code == 200
    assert response.json['job']['id'] == job['id']
    assert response.json['job']['names'] == []


def test_global_render_capacity_and_queue_bound(setup, monkeypatch):
    queued()
    queued("b" * 32)
    with pytest.raises(jobs.Busy):
        queued("c" * 32)
    clock = jobs.get("a" * 32)["created"] + 21
    monkeypatch.setattr(jobs.time, "time", lambda: clock)
    first = jobs.claim("render")
    assert first is not None
    assert jobs.claim("render") is None
    # Colab can still take the independent second job.
    assert jobs.claim("colab:worker", versions())["id"] != first["id"]


def test_worker_catalogue_mismatch_is_not_dispatched(setup):
    queued()
    assert jobs.claim("colab:old-worker", {"full": "old-version"}) is None


def test_worker_exception_hands_off_same_job(setup):
    queued()
    job = jobs.claim("colab:worker", versions())
    jobs.checkpoint(job["id"], job["token"], 0, [hit()])
    jobs.release(job["id"], job["token"])
    fallback = jobs.claim("render")
    assert fallback["id"] == job["id"]
    assert fallback["names"] == ["GitHub"]


def test_cancellation_fences_remote_and_finalizer(setup):
    queued()
    remote = jobs.claim("colab:worker", versions())
    jobs.fail(remote["id"], cancelled=True)
    with pytest.raises(jobs.LostLease):
        jobs.heartbeat(remote["id"], remote["token"])
    assert jobs.claim("render") is None


def test_paid_admission_and_refund_are_each_once(setup):
    memory, _ = setup
    memory.set("web/users/u", {"extended": {"scans_left": 2}})
    job_id = "a" * 32
    assert plans.consume_extended_scan("u", job_id) == "extended_pack"
    assert plans.consume_extended_scan("u", job_id) == "extended_pack"
    assert plans.get_account("u")["extended_scans_left"] == 1
    plans.refund_full_scan("u", "extended_pack", job_id)
    plans.refund_full_scan("u", "extended_pack", job_id)
    assert plans.get_account("u")["extended_scans_left"] == 2


def test_standard_and_guest_admission_retry_do_not_charge_twice(setup):
    source = plans.consume_standard_scan("u", "a" * 32)
    assert plans.consume_standard_scan("u", "a" * 32) == source
    assert plans.get_account("u")["standard_scans_left"] == 4
    plans.refund_full_scan("u", source, "a" * 32)
    plans.refund_full_scan("u", source, "a" * 32)
    assert plans.get_account("u")["standard_scans_left"] == 5
    assert plans.consume_guest_scan("192.0.2.1", "b" * 32) == 4
    assert plans.consume_guest_scan("192.0.2.1", "b" * 32) == 4
    assert plans.consume_guest_scan("192.0.2.1") == 3


def test_worker_endpoint_auth_and_no_customer_secrets_in_claim(setup):
    _, client = setup
    queued(uid="private-user")
    payload = {"worker_id": "worker-id-is-long-enough", "catalogues": versions(), "protocol": 1}
    assert client.post("/api/scan-worker/claim", json=payload).status_code == 401
    response = client.post("/api/scan-worker/claim", json=payload,
                           headers={"Authorization": "Bearer " + config.SCAN_WORKER_TOKEN})
    assert response.status_code == 200
    job = response.json["job"]
    assert job["username"] == "fixture"
    assert not {"uid", "owner", "charged", "refs", "FIREBASE_SERVICE_ACCOUNT"}.intersection(job)


def test_worker_payload_validation_and_disabled_mode(setup, monkeypatch):
    _, client = setup
    queued()
    remote = jobs.claim("colab:worker", versions())
    auth = {"Authorization": "Bearer " + config.SCAN_WORKER_TOKEN}
    base = {"job_id": remote["id"], "lease_token": remote["token"], "sequence": 0}
    for rows in ([hit("unknown")], [hit()] * 33, "not-a-list"):
        assert client.post("/api/scan-worker/checkpoint", json={**base, "rows": rows},
                           headers=auth).status_code == 422
    assert client.post("/api/scan-worker/checkpoint", json={**base, "rows": [hit()]},
                       headers=auth).status_code == 200
    jobs.fail(remote["id"], cancelled=True)
    assert client.post("/api/scan-worker/heartbeat", json=base, headers=auth).status_code == 409
    monkeypatch.setattr(config, "SCAN_OFFLOAD_ENABLED", False)
    assert client.post("/api/scan-worker/claim", json={}, headers=auth).status_code == 401


def test_memory_storage_refused_in_production(setup, monkeypatch):
    _, client = setup
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    response = client.post("/api/username/stream", json={"username": "fixture", "scope": "full"})
    assert response.status_code == 503
    assert not storage.store.get(jobs.ROOT)


def test_api_replay_resumes_same_job_and_ownership_is_enforced(setup, monkeypatch):
    _, client = setup
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "u"})
    body = {"username": "fixture", "scope": "full", "request_id": "request-id-long-enough"}
    first = client.post("/api/username/stream", json=body, buffered=False)
    job_event = json.loads(next(first.response))
    first.close()
    job_id = job_event["job_id"]
    again = client.post("/api/username/stream", json=body, buffered=False)
    assert json.loads(next(again.response))["job_id"] == job_id
    again.close()
    assert plans.get_account("u")["standard_scans_left"] == 4
    assert client.get(f"/api/username/jobs/{job_id}").status_code == 200
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "different-user"})
    assert client.get(f"/api/username/jobs/{job_id}").status_code == 404
    assert client.delete(f"/api/username/jobs/{job_id}").status_code == 404


def test_finalizer_uses_saved_checks_preserves_server_optional_features(setup, monkeypatch):
    queued()
    remote = jobs.claim("colab:worker", versions())
    complete_raw(remote)
    finalizer = jobs.claim("render")
    calls = []
    monkeypatch.setattr(search, "_run_full", lambda username, **kw:
        (calls.append(kw), {"status": "ok", "query": {"username": username, "scope": "full"},
                           "summary": {}, "results": {"profiles": [], "mentions": []}})[1])
    scan_job_runner.execute(finalizer)
    job = jobs.get(remote["id"])
    assert job["status"] == "complete"
    assert len(calls[0]["sweep_results"][0]) == 2
    assert job["history_id"] == remote["id"]
    assert history.list_scans("u")[0]["id"] == remote["id"]
    assert jobs.result(job)["status"] == "ok"


def test_guest_stream_and_result_do_not_leak_locked_platforms(setup, monkeypatch):
    _, client = setup
    monkeypatch.setattr(api, "_signed_in_user", lambda: None)
    body = {"username": "fixture", "scope": "standard", "request_id": "guest-request-long-enough"}
    response = client.post("/api/username/stream", json=body, buffered=False)
    job_id = json.loads(next(response.response))["job_id"]
    response.close()
    remote = jobs.claim("colab:worker", versions())
    complete_raw(remote)
    finalizer = jobs.claim("render")
    full = {"status": "ok", "query": {}, "results": {"profiles": [
        {"platform": "SecretOutsidePreview", "url": "https://example.com/fixture"}]},
        "exposures": [{"email": "private@example.com"}], "platform_checks": []}
    jobs.finish(job_id, finalizer["token"], full)
    result = client.get(f"/api/username/jobs/{job_id}").json["data"]
    assert len(result["results"]["profiles"]) == 0
    assert "exposures" not in result
    assert "private@example.com" not in json.dumps(result)
    assert result["guest_preview"]["visible_cards"] == 0


def test_render_fallback_skips_completed_checkpoints(setup, monkeypatch):
    queued()
    remote = jobs.claim("colab:worker", versions())
    jobs.checkpoint(remote["id"], remote["token"], 0, [hit()])
    jobs.release(remote["id"], remote["token"])
    fallback = jobs.claim("render")
    seen = []
    def batches(*args, **kwargs):
        seen.extend(args[3])
        yield [hit("Reddit", "not_found")]
    monkeypatch.setattr(scan_engine, "enumerate_batches", batches)
    scan_job_runner.execute(fallback)
    assert seen == ["GitHub"]
    assert jobs.get(remote["id"])["status"] == "raw_done"


def test_failed_job_refunded_after_coordinator_restart(setup):
    memory, _ = setup
    memory.set("web/users/u", {"extended": {"scans_left": 1}})
    job = queued(scope="extended")
    source = plans.consume_extended_scan("u", job["id"])
    # Admission metadata is normally persisted by the API.
    def charged(current):
        current[job["id"]]["charged"] = source
        return current
    memory.transaction(jobs.ROOT, charged)
    jobs.fail(job["id"])
    scan_job_runner.maintenance()
    scan_job_runner.maintenance()
    assert plans.get_account("u")["extended_scans_left"] == 1


def test_enumerator_never_probes_committed_rows(setup, monkeypatch):
    called = []
    monkeypatch.setattr(scan_engine.Sweep, "probe", lambda self, p:
                        (called.append(p["name"]), hit(p["name"], "not_found"))[1])
    batches = list(scan_engine.enumerate_batches("fixture", "full", completed=["GitHub"],
                                                concurrency=1, deadline_seconds=5))
    assert called == ["Reddit"]
    assert len([r for batch in batches for r in batch]) == 1


def test_worker_client_refuses_redirects_and_lease_loss(setup):
    from tools.colab_worker import Worker, LeaseLost
    class HTTP:
        def post(self, url, **kwargs):
            assert kwargs["allow_redirects"] is False
            class Response:
                status_code = 409
            return Response()
    client = Worker("https://myrecon.onrender.com", config.SCAN_WORKER_TOKEN, http=HTTP())
    with pytest.raises(LeaseLost):
        client.call("heartbeat", {})
    with pytest.raises(ValueError):
        Worker("http://example.com", config.SCAN_WORKER_TOKEN)


def test_admission_recovers_after_charge_before_queue_publish(setup, monkeypatch):
    memory, _ = setup
    job_id = "d" * 32
    memory.set("web/users/u", {"extended": {"scans_left": 2}})
    job = jobs.reserve(job_id, "fixture", "extended", False, "owner", "u")
    plans.consume_extended_scan("u", job_id)
    monkeypatch.setattr(jobs.time, "time", lambda: job["created"] + 61)
    scan_job_runner.maintenance()
    assert jobs.get(job_id)["status"] == "queued"
    assert jobs.get(job_id)["charged"] == "extended_pack"
    assert plans.get_account("u")["extended_scans_left"] == 1


def test_offloaded_cache_hit_keeps_existing_extended_credit_policy(setup, monkeypatch):
    memory, client = setup
    monkeypatch.setattr(config, "CACHE_ENABLED", True)
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "u"})
    memory.set("web/users/u", {"extended": {"scans_left": 1}})
    api._cache.set(api._cache_key("username_extended", "cached-fixture"),
                   {"status": "ok", "query": {}, "summary": {}, "results": {}})
    response = client.post("/api/username/stream", json={"username": "cached-fixture", "scope": "extended"})
    assert json.loads(response.data)["type"] == "complete"
    assert plans.get_account("u")["extended_scans_left"] == 1
    assert not memory.get(jobs.ROOT)


def test_colab_client_to_api_to_final_report_round_trip(setup, monkeypatch):
    from urllib.parse import urlsplit
    from tools.colab_worker import Worker
    memory, client = setup
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "u"})
    monkeypatch.setattr(scan_engine.Sweep, "probe", lambda self, p: hit(p["name"],
                        "found" if p["name"] == "GitHub" else "not_found"))
    monkeypatch.setattr(search, "_enrich_profiles", lambda *a, **k: None)
    monkeypatch.setattr(search, "_code_exposure", lambda *a, **k: [])
    class HTTP:
        def post(self, url, **kwargs):
            response = client.post(urlsplit(url).path, json=kwargs["json"], headers=kwargs["headers"])
            class Response:
                status_code = response.status_code
                def json(self): return response.json
                def raise_for_status(self):
                    assert 200 <= response.status_code < 300, response.json
            return Response()
        def close(self): pass
    stream = client.post("/api/username/stream", json={"username": "fixture", "scope": "full",
                          "request_id": "round-trip-request-id"}, buffered=False)
    job_id = json.loads(next(stream.response))["job_id"]
    stream.close()
    worker = Worker("https://myrecon.onrender.com", config.SCAN_WORKER_TOKEN, http=HTTP())
    remote = worker.call("claim", {"worker_id": worker.worker_id,
                                  "catalogues": worker.catalogues, "protocol": 1})["job"]
    worker.execute(remote)
    finalizer = jobs.claim("render")
    scan_job_runner.execute(finalizer)
    result = client.get(f"/api/username/jobs/{job_id}").json
    assert result["job_status"] == "complete"
    assert result["data"]["coverage"]["total"] == 2
    assert result["data"]["coverage"]["unchecked"] == 0
    assert result["data"]["results"]["profiles"][0]["platform"] == "GitHub"
    assert len(history.list_scans("u")) == 1
    assert plans.get_account("u")["standard_scans_left"] == 4


def test_delete_history_removes_job_payload_without_refunding_or_recreating(setup):
    memory, _ = setup
    memory.set("web/users/u", {"extended": {"scans_left": 2}})
    job = queued(scope="extended")
    source = plans.consume_extended_scan("u", job["id"])
    def charged(current):
        current[job["id"]]["charged"] = source
        return current
    memory.transaction(jobs.ROOT, charged)
    remote = jobs.claim("colab:worker", versions())
    complete_raw(remote)
    finalizer = jobs.claim("render")
    data = {"query": {"username": "fixture"}, "summary": {}, "results": {}}
    jobs.finish(job["id"], finalizer["token"], data)
    history.save("u", data, scan_id=job["id"])
    history.delete("u", job["id"])
    assert jobs.get(job["id"])["status"] == "deleted"
    assert not memory.get(f"{jobs.DATA}/{job['id']}")
    scan_job_runner.maintenance()
    assert plans.get_account("u")["extended_scans_left"] == 1
    assert jobs.reserve(job["id"], "fixture", "extended", False, "owner", "u")["status"] == "deleted"


def test_stream_limit_refuses_before_admission_and_releases_on_disconnect(setup, monkeypatch):
    _, client = setup
    monkeypatch.setattr(api, "_signed_in_user", lambda: {"sub": "u"})
    monkeypatch.setattr(scan_job_api, "_wait_slots", threading.BoundedSemaphore(1))
    body = {"username": "fixture", "scope": "full", "request_id": "bounded-connections-request"}
    first = client.post("/api/username/stream", json=body, buffered=False)
    next(first.response)
    refusal = client.post("/api/username/stream", json={**body, "request_id": "other-connections-request"})
    assert refusal.status_code == 429
    assert plans.get_account("u")["standard_scans_left"] == 4
    first.close()
    second = client.post("/api/username/stream", json=body, buffered=False)
    assert second.status_code == 200
    next(second.response)
    second.close()


def test_completed_report_history_is_recovered_after_save_failure(setup, monkeypatch):
    queued()
    remote = jobs.claim("colab:worker", versions())
    complete_raw(remote)
    finalizer = jobs.claim("render")
    monkeypatch.setattr(search, "_run_full", lambda *a, **k: {
        "status": "ok", "query": {"username": "fixture"}, "summary": {}, "results": {}})
    real_save = history.save
    monkeypatch.setattr(history, "save", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    scan_job_runner.execute(finalizer)
    assert jobs.get(remote["id"])["status"] == "complete"
    assert not jobs.get(remote["id"]).get("history_id")
    monkeypatch.setattr(history, "save", real_save)
    scan_job_runner.maintenance()
    assert jobs.get(remote["id"])["history_id"] == remote["id"]
