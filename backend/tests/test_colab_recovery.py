import ast
import io
from pathlib import Path
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


def test_disabled_recovery_never_starts_thread(monkeypatch):
    monkeypatch.delenv("COLAB_AUTO_RECOVERY_ENABLED", raising=False)
    monkeypatch.setattr(recovery.threading, "Thread", lambda **kw: (_ for _ in ()).throw(AssertionError()))
    recovery.ensure_started()


def test_assignment_identity_is_stable_and_token_specific():
    assert controller.notebook_id("a" * 48) == controller.notebook_id("a" * 48)
    assert controller.notebook_id("a" * 48) != controller.notebook_id("b" * 48)


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


def test_child_status_discards_provider_text_and_credentials():
    from types import SimpleNamespace
    recovery.read_stages(SimpleNamespace(stdout=io.StringIO(
        "authorizing\nprovider error containing secret\nworker-live\n")))
    assert recovery.status()["stage"] == "worker-live"


def test_recovery_status_requires_operator_token(monkeypatch):
    import app as api
    import config
    monkeypatch.setattr(config, "SCAN_WORKER_STATUS_TOKEN", "status-token-" * 4)
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
