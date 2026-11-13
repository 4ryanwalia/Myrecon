"""Privacy regressions across paid/free scans, worker delivery and counters."""
import json
import pytest
import app as api
from core import android_billing, cache, guest_reports, history, match_choices, plans, privacy_cleanup
from core import scan_jobs as jobs, store as storage
from services import scan_job_api

@pytest.fixture
def stores(monkeypatch):
    account = storage._MemoryStore()
    queue = storage._MemoryStore()
    monkeypatch.setattr(storage, "store", account)
    monkeypatch.setattr(plans, "store", account)
    monkeypatch.setattr(jobs, "_job_store", queue)
    return account, queue

@pytest.mark.parametrize("uid", [None, "free", "subscriber"])
def test_completed_scan_records_only_count(stores, uid):
    account, _ = stores
    data = {"status": "ok", "query": {"email": "private@example.test"},
            "results": {"secret": "sensitive result"}}
    for _ in range(2):
        assert api._remember(uid, data) is None
        assert history.save(uid, data) is None
    encoded = json.dumps(account._data)
    assert "private@example.test" not in encoded and "sensitive result" not in encoded
    path = f"web/users/{uid}" if uid else "web/usage/guest"
    assert account.get(path) == {"scan_count": 2}
    assert history.list_scans(uid) == []
    with pytest.raises(history.NotFound): history.get(uid, "legacy")


def test_free_account_read_does_not_create_profile(stores):
    account, _ = stores
    assert plans.get_account("free", "account@example.test", "Person")["scan_count"] == 0
    assert not account._data


def test_cache_and_guest_report_cannot_retain_payload():
    payload = {"subject": "private@example.test", "results": ["secret"]}
    c = cache.TTLCache()
    c.set("private", payload)
    assert c.get("private") is None and not c._store
    receipt = guest_reports.retain("email", payload)
    assert receipt["report_token"] is None
    assert guest_reports.read(receipt["report_token"]) is None


def test_worker_buffer_is_memory_only_and_erased_on_delivery(stores):
    account, queue = stores
    data = {"status": "ok", "query": {"username": "private-handle"}}
    queue.set(jobs.ROOT, {"job": {"id": "job", "uid": "paid", "status": "complete",
        "result_token": "token", "history_id": None}})
    queue.set(f"{jobs.DATA}/job/results/token", data)
    events = list(scan_job_api.events(api, "job"))
    assert json.loads(events[-1])["data"] == data
    assert jobs.get("job") is None
    assert queue.get(f"{jobs.DATA}/job/results/token") is None
    assert not account._data


def test_mobile_counter_ignores_extra_fields_and_retries_are_idempotent(stores):
    account, _ = stores
    account.backend = "rtdb"
    install = "11111111-1111-1111-1111-111111111111"
    for count in (3, 3, 2):
        android_billing.record_scan_count({"install_id": install, "scan_count": count,
                                          "username": "do-not-store", "results": ["secret"]})
    assert account.get(f"android_usage/{install}/scan_count") == 3
    assert "do-not-store" not in json.dumps(account._data)
    assert "secret" not in json.dumps(account._data)


def test_migration_erases_legacy_scans_and_preserves_entitlements(stores, monkeypatch):
    account, _ = stores
    account.backend = "rtdb"
    for path in privacy_cleanup.SCAN_PATHS:
        account.set(path, {"secret": "legacy search"})
    account.set("web/users/free", {"email": "free@example.test", "name": "Free", "scan_count": 2})
    paid = {"email": "paid@example.test", "extended": {"scans_left": 3}, "scan_count": 4}
    account.set("web/users/paid", paid)
    privacy_cleanup.run()
    for path in privacy_cleanup.SCAN_PATHS: assert account.get(path) is None
    assert account.get("web/users/free") == {"scan_count": 2}
    assert account.get("web/users/paid") == paid
    assert privacy_cleanup.status() == "complete"
    privacy_cleanup.run()
    assert account.get("web/users/paid") == paid


def test_restart_refunds_interrupted_credit_using_metadata_only(stores):
    account, queue = stores
    account.set("web/users/u", {"extended": {"scans_left": 2}})
    jobs.reserve("job", "private-handle", "extended", False, "owner", "u")
    source = plans.consume_extended_scan("u", job_id="job")
    assert plans.get_account("u")["extended_scans_left"] == 1
    jobs.discard("job")
    assert plans.get_account("u")["extended_scans_left"] == 2
    assert plans.get_account("u")["extended_scans_left"] == 2
    assert "private-handle" not in json.dumps(account._data)


def test_completed_job_count_and_receipt_settle_atomically(stores):
    account, queue = stores
    account.set("web/users/u", {"extended": {"scans_left": 2}})
    jobs.reserve("job", "private-handle", "extended", False, "owner", "u")
    plans.consume_extended_scan("u", job_id="job")
    plans.record_scan("u", job_id="job")
    plans.record_scan("u", job_id="job")
    jobs.discard("job")
    result = plans.get_account("u")
    assert result["scan_count"] == 1 and result["extended_scans_left"] == 1
