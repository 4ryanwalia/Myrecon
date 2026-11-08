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
_lock = threading.Lock()
_status = {"stage": "disabled", "updated_at": 0}
_STAGES = {"authorizing", "assigned", "bootstrapping", "worker-live", "render-unavailable"}


def note(stage):
    with _lock:
        _status.update(stage=stage, updated_at=int(time.time()))


def status():
    with _lock:
        return dict(_status)


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
        except Exception:
            note("controller-error")
            # Never log provider exception text, tokens or source sent to Jupyter.
            log.warning("Colab recovery paused after a controller/lease failure.")
            delay = min(900, delay * 2)
        finally:
            stop_child(child)
        time.sleep(delay)


def ensure_started():
    global _started
    if os.getenv("COLAB_AUTO_RECOVERY_ENABLED", "").lower() != "true":
        return
    from core.scan_jobs import available
    if not available() or storage.store.backend != "rtdb":
        log.warning("Colab recovery requires the durable scan queue.")
        return
    if not os.getenv("COLAB_GOOGLE_CREDENTIALS_JSON"):
        log.warning("Colab recovery is waiting for Google authorization.")
        return
    with _lock:
        if not _started:
            _started = True
            threading.Thread(target=supervise, name="colab-recovery", daemon=True).start()
