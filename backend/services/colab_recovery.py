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
_child = None
_last_error = None
_last_stdout_line = None
_last_code = None
_last_stderr = None
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
    import sys, traceback
    stack = None
    if _thread and _thread.ident and _thread.ident in sys._current_frames():
        stack = [f"{Path(f.filename).name}:{f.lineno} in {f.name}"
                 for f in traceback.extract_stack(sys._current_frames()[_thread.ident])[-6:]]
    all_threads = {}
    frames = sys._current_frames()
    for th in threading.enumerate():
        if th.ident and th.ident in frames:
            all_threads[th.name] = [f"{Path(f.filename).name}:{f.lineno} in {f.name}"
                                    for f in traceback.extract_stack(frames[th.ident])[-5:]]
    data["diagnostics"] = {
        "enabled": _is_enabled(),
        "storage_backend": storage.store.backend,
        "jobs_available": available(),
        "has_google_credentials": bool(os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON")),
        "has_worker_token": bool(os.getenv("SCAN_WORKER_TOKEN")),
        "thread_alive": bool(_thread and _thread.is_alive()),
        "executable_exists": executable.exists(),
        "last_error": _last_error,
        "last_stdout": _last_stdout_line,
        "last_code": _last_code,
        "last_stderr": _last_stderr,
        "thread_stack": stack,
        "child_running": bool(_child and _child.poll() is None),
        "all_threads": all_threads,
        "lease": storage.store.get(ROOT),
        "server_now": int(time.time()),
    }
    return data


def read_stages(child):
    global _last_stdout_line
    for line in iter(lambda: child.stdout.readline(4096), ""):
        stripped = line.strip()
        _last_stdout_line = stripped[:64]
        if stripped in _STAGES:
            note(stripped)
            log.info("Colab recovery: %s", stripped)


def renew(owner, now=None):
    now = time.time() if now is None else now

    def change(current):
        current = current or {}
        expires_at = current.get("expires_at", 0)
        if current.get("owner") != owner and now < expires_at <= now + LEASE_SECONDS * 2:
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
    global _last_error, _child, _last_code, _last_stderr
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
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                _child = child
                threading.Thread(target=read_stages, args=(child,), daemon=True).start()
                started = time.monotonic()
                while child.poll() is None:
                    time.sleep(20)
                    if not renew(owner) or time.monotonic() - started > 11 * 3600:
                        stop_child(child)
                        break
                code = child.returncode
                _last_code = code
                if code != 0 and child.stderr:
                    try:
                        _last_stderr = child.stderr.read(512).strip()
                    except Exception:
                        pass
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
                _child = None
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
