"""One recoverable Render fallback/finalizer, with cross-process leases."""
import logging
import threading
import time

import config
from core import history, plans, scan_jobs as jobs, store as storage
from services import scan_engine

log = logging.getLogger("myrecon.scan_jobs")
_lock = threading.Lock()
_thread = None


def refund(job):
    if job and job.get("status") in ("failed", "cancelled"):
        receipt = plans.job_receipt(job.get("uid"), job["id"])
        source = job.get("charged") or (receipt or {}).get("source")
        if source:
            plans.refund_full_scan(job.get("uid"), source, job_id=job["id"])


def execute(job):
    """Heartbeat on a separate thread even while a provider is slow."""
    stop = threading.Event()
    lost = threading.Event()
    job_id, token = job["id"], job["token"]

    def renew():
        while not stop.wait(10):
            try:
                jobs.heartbeat(job_id, token)
            except Exception:
                lost.set()
                return

    monitor = threading.Thread(target=renew, daemon=True)
    monitor.start()
    try:
        if job["status"] == "scanning":
            deadline = (config.SWEEP_EXTENDED_DEADLINE_SECONDS if job["scope"] == "extended"
                        else config.SWEEP_FULL_DEADLINE_SECONDS if job["scope"] == "full" else 120)
            batch, sequence, flushed = [], 0, time.monotonic()
            for rows in scan_engine.enumerate_batches(
                    job["username"], job["scope"], job["deep"], job.get("names", []),
                    concurrency=config.SWEEP_CONCURRENCY, deadline_seconds=deadline,
                    cancelled=lost.is_set):
                batch.extend(rows)
                while len(batch) >= 32:
                    jobs.checkpoint(job_id, token, sequence, batch[:32])
                    del batch[:32]
                    sequence += 1
                    flushed = time.monotonic()
                if batch and time.monotonic() - flushed >= 10:
                    jobs.checkpoint(job_id, token, sequence, batch)
                    batch = []
                    sequence += 1
                    flushed = time.monotonic()
                if lost.is_set():
                    return
            if batch:
                jobs.checkpoint(job_id, token, sequence, batch)
            if not lost.is_set():
                jobs.raw_done(job_id, token)
            return

        from services.search import _run_full, _run_username
        rows = jobs.rows(job)
        if job["scope"] == "standard":
            data = _run_username(job["username"], job["deep"], platform_results=rows)
        else:
            cov = scan_engine.coverage(rows, len(scan_engine.catalogue(job["scope"], job["deep"])))
            data = _run_full(job["username"], extended=job["scope"] == "extended",
                             sweep_results=(rows, cov))
        if lost.is_set():
            return
        data["execution"] = {"job_id": job_id, "resumed": job["attempts"] > 2}
        # Final result is persisted before the terminal status is published.
        # Deterministic history id makes a finalizer restart harmless.
        jobs.finish(job_id, token, data)
        if config.CACHE_ENABLED and not data.get("partial") and data.get("status") != "error":
            import app as api
            key = (api._cache_key("username_" + job["scope"], job["username"])
                   if job["scope"] != "standard" else api._cache_key("username", job["username"], job["deep"]))
            api._cache.set(key, data)
        if job.get("uid") and storage.persistent():
            try:
                history.save(job["uid"], data, scan_id=job_id)
                jobs.remember_history(job_id, token)
            except Exception as exc:
                log.warning("Could not save job history (%s)", type(exc).__name__)
    except jobs.LostLease:
        pass
    except Exception as exc:
        log.warning("Scan job failed (%s)", type(exc).__name__)
        try:
            refund(jobs.fail(job_id, token))
        except jobs.LostLease:
            pass
    finally:
        stop.set()
        monitor.join(timeout=1)


def maintenance():
    for job in (storage.store.get(jobs.ROOT) or {}).values():
        if job["status"] not in jobs.TERMINAL:
            # An interrupted admission/finalization must not clog the queue.
            limit = 60 if job["status"] == "admitting" else 3600
            if time.time() - job["created"] > limit:
                receipt = plans.job_receipt(job.get("uid"), job["id"])
                guest = storage.store.get(job["guest_receipt_path"]) if job.get("guest_receipt_path") else None
                guest_admitted = isinstance(guest, dict) and job["id"] in (guest.get("jobs") or {})
                if job["status"] == "admitting" and (receipt or guest_admitted):
                    job = jobs.admit(job["id"], (receipt or {}).get("source"))
                else:
                    job = jobs.fail(job["id"])
        refund(job)
        if job["status"] == "complete" and job.get("uid") and not job.get("history_id") and storage.persistent():
            history.save(job["uid"], jobs.result(job), scan_id=job["id"])
            jobs.remember_history(job["id"], job["result_token"])
    jobs.prune()


def ensure_started():
    global _thread
    with _lock:
        if _thread and _thread.is_alive():
            return

        def loop():
            last_maintenance = 0
            while jobs.available():
                try:
                    if time.monotonic() - last_maintenance > 60:
                        maintenance()
                        last_maintenance = time.monotonic()
                    from app import _full_slots
                    if _full_slots.acquire(blocking=False):
                        try:
                            job = jobs.claim("render")
                            if job:
                                execute(job)
                                continue
                        finally:
                            _full_slots.release()
                except Exception as exc:
                    log.warning("Scan coordinator retry (%s)", type(exc).__name__)
                time.sleep(2)

        _thread = threading.Thread(target=loop, daemon=True, name="scan-job-coordinator")
        _thread.start()
