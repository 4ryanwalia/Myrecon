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
