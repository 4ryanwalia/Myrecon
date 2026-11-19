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
LEASE_RENEW_SECONDS = 40
STARTUP_TIMEOUT = 180
PULSE_TIMEOUT = 300
MAX_SESSION_AGE = 11 * 3600
_started = False
_thread = None
_lock = threading.Lock()
_status = {"stage": "disabled", "updated_at": 0, "retry_at": None}
_STAGES = {"authorizing", "assigned", "bootstrapping", "worker-live", "render-unavailable"}


def note(stage, retry_in=None):
    with _lock:
        now = int(time.time())
        if _status["stage"] == stage and retry_in is None:
            return False
        _status.update(stage=stage, updated_at=now,
                       retry_at=now + retry_in if retry_in is not None else None)
        return True


def _is_enabled():
    val = os.getenv("COLAB_AUTO_RECOVERY_ENABLED", "").strip().lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return bool(os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON"))


def status():
    with _lock:
        data = dict(_status)
    data["diagnostics"] = {
        "enabled": _is_enabled(),
        "thread_alive": bool(_thread and _thread.is_alive()),
    }
    return data


def read_stages(child, healthy, activity):
    for line in iter(lambda: child.stdout.readline(4096), ""):
        stage = line.strip()
        if stage == "worker-live":
            healthy.set()
        elif stage == "render-unavailable":
            healthy.clear()
        if stage in {"worker-live", "worker-pulse", "render-unavailable"}:
            activity.set()
        if stage in _STAGES and note(stage):
            log.info("Colab recovery: %s", stage)


def renew(owner, now=None):
    now = time.time() if now is None else now

    def change(current):
        current = current if isinstance(current, dict) else {}
        expires_at = current.get("expires_at", 0)
        if (current.get("owner") != owner and type(expires_at) in (int, float)
                and now < expires_at <= now + LEASE_SECONDS * 2):
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


def retry_delay(previous, code, healthy=False):
    """Require a sustained live session before resetting the retry delay."""
    if code == 75:
        return 1800
    if healthy:
        return 30
    return min(900, max(60, previous * 2))


def wait_for_child(child, owner, activity, healthy):
    started = last_activity = time.monotonic()
    first_live_activity = None
    stable = False
    timeout = STARTUP_TIMEOUT
    while True:
        try:
            return child.wait(timeout=LEASE_RENEW_SECONDS), stable
        except subprocess.TimeoutExpired:
            now = time.monotonic()
        if activity.is_set():
            activity.clear()
            last_activity = now
            timeout = PULSE_TIMEOUT
            if not healthy.is_set():
                first_live_activity = None
            elif first_live_activity is None:
                first_live_activity = now
            elif now - first_live_activity >= PULSE_TIMEOUT:
                stable = True
        if now - last_activity >= timeout:
            log.warning("Colab controller stopped reporting activity.")
            return 1, stable
        if now - started >= MAX_SESSION_AGE or not renew(owner):
            return 1, stable


def supervise():
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
                healthy = threading.Event()
                activity = threading.Event()
                reader = threading.Thread(target=read_stages, args=(child, healthy, activity), daemon=True)
                reader.start()
                try:
                    code, stable = wait_for_child(child, owner, activity, healthy)
                finally:
                    stop_child(child)
                    reader.join(timeout=2)
                child = None
                if code == 78:
                    note("needs-authorization")
                    log.error("Colab recovery needs Google/worker credential configuration; disabled until restart.")
                    return
                delay = retry_delay(delay, code, stable)
                note("waiting-for-compute-units" if code == 75 else "retrying", retry_in=delay)
                log.info("Colab controller finished (code %s); retrying in %ss. Render fallback remains available.", code, delay)
            except Exception as e:
                delay = retry_delay(delay, 1)
                note("controller-error", retry_in=delay)
                # Never log provider exception text, tokens or source sent to Jupyter.
                log.warning("Colab recovery paused after a controller/lease failure (%s).", type(e).__name__)
            finally:
                stop_child(child)
            time.sleep(delay)
    except Exception as e:
        note("supervisor-fatal-error")
        log.error("Colab recovery supervisor fatal error (%s).", type(e).__name__)


def ensure_started():
    global _started, _thread
    if not _is_enabled():
        return
    from core.scan_jobs import available
    if not available() or storage.store.backend != "rtdb":
        note("offload-unavailable")
        log.warning("Colab recovery requires RTDB-backed worker coordination.")
        return
    if not os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON"):
        note("needs-authorization")
        log.warning("Colab recovery is waiting for Google authorization.")
        return
    with _lock:
        if not _started:
            _thread = threading.Thread(target=supervise, name="colab-recovery", daemon=True)
            _thread.start()
            _started = True
