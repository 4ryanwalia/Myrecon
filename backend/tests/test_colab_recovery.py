import ast
import io
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import zipfile

from core import store as storage
from services import colab_recovery as recovery
from tools import colab_controller as controller


def test_controller_lease_excludes_other_deploy_until_expiry(monkeypatch):
    store = storage._MemoryStore()
    monkeypatch.setattr(storage, "store", store)
    assert recovery.renew("old", now=100)
    assert not recovery.renew("new", now=219)
    assert recovery.renew("old", now=200)
    assert not recovery.renew("new", now=319)
    assert recovery.renew("new", now=320)
    assert not recovery.renew("old", now=321)


def test_worker_leases_are_independent(monkeypatch):
    monkeypatch.setattr(storage, "store", storage._MemoryStore())
    assert recovery.renew("primary", now=100, slot=1)
    assert recovery.renew("secondary", now=110, slot=2)
    assert not recovery.renew("replacement", now=119, slot=2)
    assert recovery.renew("replacement", now=230, slot=2)
    assert recovery.renew("primary", now=240, slot=1)
    assert not recovery.renew("replacement", now=250, slot=1)


def test_disabled_recovery_never_starts_thread(monkeypatch):
    monkeypatch.delenv("COLAB_AUTO_RECOVERY_ENABLED", raising=False)
    monkeypatch.setattr(recovery.threading, "Thread", lambda **kw: (_ for _ in ()).throw(AssertionError()))
    recovery.ensure_started()


def test_assignment_identity_is_stable_and_token_specific():
    assert controller.notebook_id("a" * 48) == controller.notebook_id("a" * 48)
    assert controller.notebook_id("a" * 48) != controller.notebook_id("b" * 48)
    assert controller.notebook_id("a" * 48) != controller.notebook_id("a" * 48, 2)


def test_configured_supervisors_start_once(monkeypatch):
    from core import scan_jobs

    started = []

    class Thread:
        def __init__(self, target, args, **kwargs):
            assert target is recovery.supervise
            self.args = args

        def start(self):
            started.extend(self.args)

    monkeypatch.setenv("COLAB_AUTO_RECOVERY_ENABLED", "true")
    monkeypatch.setenv("COLAB_GOOGLE_CREDENTIALS_JSON", "{}")
    monkeypatch.delenv("COLAB_AUTO_RECOVERY_WORKERS", raising=False)
    monkeypatch.setattr(recovery, "_threads", {})
    monkeypatch.setattr(recovery.threading, "Thread", Thread)
    monkeypatch.setattr(scan_jobs, "available", lambda: True)
    monkeypatch.setattr(storage, "store", SimpleNamespace(backend="rtdb"))
    recovery.ensure_started()
    recovery.ensure_started()
    assert started == [1, 2]
    monkeypatch.setenv("COLAB_AUTO_RECOVERY_WORKERS", "1")
    assert recovery.configured_slots() == (1,)


def test_remote_bootstrap_runs_matching_bundle_without_google_credentials(tmp_path):
    from tools.build_colab_bundle import FILES, build
    archive = build(tmp_path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert set(FILES).issubset(bundle.namelist())
    code = controller.bootstrap(archive, "https://myrecon.onrender.com", "test-token-" * 5)
    ast.parse(code)
    assert "duration_minutes=600" in code
    assert "Auto CPU worker" in code
    assert "COLAB_GOOGLE_CREDENTIALS_JSON" not in code
    assert "FIREBASE" not in code
    assert "google.colab import userdata" not in code


def test_child_termination_waits_before_releasing_control():
    events = []

    class Child:
        def poll(self):
            return None

        def terminate(self):
            events.append("terminate")

        def wait(self, timeout):
            events.append("wait")

    recovery.stop_child(Child())
    assert events == ["terminate", "wait"]


def test_child_status_discards_provider_text_and_credentials(monkeypatch):
    monkeypatch.setattr(recovery, "_status", dict(recovery._status))
    child = SimpleNamespace(stdout=io.StringIO(
        "authorizing\nprovider error containing secret\nworker-live\nworker-pulse\n"))
    recovery.read_stages(child, threading.Event(), threading.Event())
    snapshot = recovery.status()
    assert snapshot["stage"] == "worker-live"
    assert "secret" not in str(snapshot)
    recovery.note("bootstrapping", slot=2)
    assert [(row["slot"], row["stage"]) for row in recovery.status()["workers"]] == [
        (1, "worker-live"), (2, "bootstrapping"),
    ]


def test_recovery_status_requires_operator_token(monkeypatch):
    import app as api
    import config
    monkeypatch.setattr(config, "SCAN_WORKER_STATUS_TOKEN", "status-token-" * 4)
    monkeypatch.setattr(recovery, "ensure_started", lambda: (_ for _ in ()).throw(AssertionError()))
    client = api.app.test_client()
    assert client.get("/api/operator/colab-recovery").status_code == 401
    response = client.get("/api/operator/colab-recovery", headers={
        "Authorization": "Bearer " + config.SCAN_WORKER_STATUS_TOKEN})
    assert response.status_code == 200
    assert "secret" not in response.get_data(as_text=True)
    payload = response.get_json()
    assert "diagnostics" in payload
    assert "enabled" in payload["diagnostics"]


def test_is_enabled_respects_flags_and_credentials(monkeypatch):
    monkeypatch.delenv("COLAB_AUTO_RECOVERY_ENABLED", raising=False)
    monkeypatch.delenv("COLAB_GOOGLE_CREDENTIALS_JSON", raising=False)
    assert not recovery._is_enabled()

    monkeypatch.setenv("COLAB_GOOGLE_CREDENTIALS_JSON", '{"type":"authorized_user"}')
    assert recovery._is_enabled()

    monkeypatch.setenv("COLAB_AUTO_RECOVERY_ENABLED", "false")
    assert not recovery._is_enabled()

    monkeypatch.setenv("COLAB_AUTO_RECOVERY_ENABLED", "true")
    assert recovery._is_enabled()


def test_recovery_backoff_resets_after_live_worker():
    healthy = threading.Event()
    recovery.read_stages(SimpleNamespace(stdout=io.StringIO("worker-live\n")), healthy, threading.Event())
    assert healthy.is_set()
    assert recovery.retry_delay(900, 1, True) == 30
    assert recovery.retry_delay(60, 1) == 120
    assert recovery.retry_delay(900, 1) == 900
    assert recovery.retry_delay(60, 0) == 120
    assert recovery.retry_delay(900, 75, True) == 1800


def test_supervisor_times_out_only_after_worker_goes_silent(monkeypatch):
    activity = threading.Event()
    healthy = threading.Event()
    now = 0
    renewals = []

    class Child:
        def wait(self, timeout):
            nonlocal now
            now += timeout
            if now <= 480:
                activity.set()
                healthy.set()
            raise subprocess.TimeoutExpired("controller", timeout)

    monkeypatch.setattr(recovery.time, "monotonic", lambda: now)
    monkeypatch.setattr(recovery, "renew", lambda owner, **kwargs: renewals.append(now) or True)
    assert recovery.wait_for_child(Child(), "owner", activity, healthy) == (1, True)
    assert 480 + recovery.PULSE_TIMEOUT <= now < 480 + recovery.PULSE_TIMEOUT + recovery.LEASE_RENEW_SECONDS
    assert renewals[-1] == now - recovery.LEASE_RENEW_SECONDS


def test_supervisor_times_out_a_silent_startup_without_resetting_backoff(monkeypatch):
    activity = threading.Event()
    healthy = threading.Event()
    now = 0

    class Child:
        def wait(self, timeout):
            nonlocal now
            now += timeout
            raise subprocess.TimeoutExpired("controller", timeout)

    monkeypatch.setattr(recovery.time, "monotonic", lambda: now)
    monkeypatch.setattr(recovery, "renew", lambda owner, **kwargs: True)
    assert recovery.wait_for_child(Child(), "owner", activity, healthy) == (1, False)
    assert recovery.STARTUP_TIMEOUT <= now < recovery.STARTUP_TIMEOUT + recovery.LEASE_RENEW_SECONDS
