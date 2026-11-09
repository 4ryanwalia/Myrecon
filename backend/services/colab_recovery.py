"""Opt-in Render supervisor. Google credentials stay in an isolated child."""
import logging
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time

from core import store as storage
from core.store import Abort

log = logging.getLogger("myrecon.colab_recovery")
ROOT = "web/colab_controller"
LEASE_SECONDS = 120
_started = False
_thread = None
_last_error = None
_lock = threading.Lock()
_status = {"stage": "disabled", "updated_at": 0}
_STAGES = {"authorizing", "assigned", "bootstrapping", "worker-live", "render-unavailable"}


def note(stage):
    with _lock:
        _status.update(stage=stage, updated_at=int(time.time()))


def _is_enabled():
    val = os.getenv("COLAB_AUTO_RECOVERY_ENABLED", "").strip().lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return bool(os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON"))


def status():
    ensure_started()
    with _lock:
        data = dict(_status)
    from core.scan_jobs import available
    backend = Path(__file__).resolve().parents[1]
    executable = backend / ".venv/colab/bin/python"
    data["diagnostics"] = {
        "enabled": _is_enabled(),
        "storage_backend": storage.store.backend,
        "jobs_available": available(),
        "has_google_credentials": bool(os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON")),
        "thread_alive": bool(_thread and _thread.is_alive()),
        "executable_exists": executable.exists(),
        "last_error": _last_error,
    }
    return data


def read_stages(child):
    for line in iter(lambda: child.stdout.readline(4096), ""):
        stage = line.strip()
        if stage in _STAGES:
            note(stage)
            log.info("Colab recovery: %s", stage)


def renew(owner, now=None):
    now = time.time() if now is None else now

    def change(current):
        current = current or {}
        if current.get("owner") != owner and current.get("expires_at", 0) > now:
            raise Abort()
        return {"owner": owner, "expires_at": now + LEASE_SECONDS}

    try:
        storage.store.transaction(ROOT, change)
        return True
    except Abort:
        return False


def stop_child(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def supervise():
    global _last_error
    note("supervisor-booting")
    try:
        owner = secrets.token_hex(16)
        backend = Path(__file__).resolve().parents[1]
        executable = backend / ".venv/colab/bin/python"
        delay = 60
        while True:
            child = None
            try:
                if not renew(owner):
                    note("waiting-for-controller-lease")
                    time.sleep(30)
                    continue
                # The scanner child receives no Firebase, payment or search secrets.
                allowed = ("PATH", "HOME", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR",
                           "COLAB_GOOGLE_CREDENTIALS_JSON", "SCAN_WORKER_TOKEN",
                           "COLAB_API_ORIGIN")
                env = {key: os.environ[key] for key in allowed if key in os.environ}
                env["PYTHONUNBUFFERED"] = "1"
                note("starting")
                child = subprocess.Popen([str(executable), "tools/colab_controller.py"],
                    cwd=backend, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                threading.Thread(target=read_stages, args=(child,), daemon=True).start()
                started = time.monotonic()
                while child.poll() is None:
                    time.sleep(20)
                    if not renew(owner) or time.monotonic() - started > 11 * 3600:
                        stop_child(child)
                        break
                code = child.returncode
                if code == 78:
                    note("needs-authorization")
                    log.error("Colab recovery needs Google/worker credential configuration; disabled until restart.")
                    return
                delay = 1800 if code == 75 else min(900, delay * 2)
                if code == 0:
                    delay = 30
                note("waiting-for-compute-units" if code == 75 else "retrying")
                log.info("Colab controller finished (code %s); retrying in %ss. Render fallback remains available.", code, delay)
            except Exception as e:
                _last_error = f"{type(e).__name__}: {e}"
                note("controller-error")
                # Never log provider exception text, tokens or source sent to Jupyter.
                log.warning("Colab recovery paused after a controller/lease failure (%s).", type(e).__name__)
                delay = min(900, delay * 2)
            finally:
                stop_child(child)
            time.sleep(delay)
    except BaseException as e:
        _last_error = f"FATAL_{type(e).__name__}: {e}"
        note("supervisor-fatal-error")
        log.exception("Colab recovery supervisor fatal error")


def ensure_started():
    global _started, _thread
    if not _is_enabled():
        return
    from core.scan_jobs import available
    if not available() or storage.store.backend != "rtdb":
        log.warning("Colab recovery requires the durable scan queue.")
        return
    if not os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON"):
        log.warning("Colab recovery is waiting for Google authorization.")
        return
    with _lock:
        if _thread is None or not _thread.is_alive():
            _started = True
            _thread = threading.Thread(target=supervise, name="colab-recovery", daemon=True)
            _thread.start()
