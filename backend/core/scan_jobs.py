"""Durable, leased scan queue. Only Render owns the database credentials.

All ownership transitions share one small RTDB transaction. Checkpoint data
is written separately under an attempt token, then atomically referenced.
An expired worker cannot overwrite a replacement's progress or results.
"""
import hashlib
import json
import math
import secrets
import time
from functools import lru_cache

import config
from core import store as storage
from core.store import Abort
from services import scan_engine

ROOT = "web/scan_dispatch"
DATA = "web/scan_job_data"
TERMINAL = {"complete", "failed", "cancelled", "deleted"}
_ACTIVE = {"admitting", "queued", "scanning", "raw_done", "finalizing"}


class Busy(Exception):
    pass


class LostLease(Exception):
    pass


def available():
    return (config.SCAN_OFFLOAD_ENABLED and len(config.SCAN_WORKER_TOKEN) >= 32
            and (storage.store.backend == "rtdb" or not config.IS_PRODUCTION))


@lru_cache(maxsize=8)
def engine_fingerprint(scope, deep=False):
    """The immutable deployed engine revision, shared by queue/status calls."""
    return scan_engine.fingerprint(scope, deep)


def _timestamp(value):
    return type(value) in (int, float) and 0 <= value < 1e20 and math.isfinite(value)


def _dispatchable(job):
    # Retained terminal records need no dispatcher schema. A malformed old
    # record must not prevent healthy jobs from being claimed.
    return (isinstance(job, dict) and isinstance(job.get("status"), str)
            and job["status"] in _ACTIVE
            and job.get("scope") in ("standard", "full", "extended")
            and type(job.get("deep")) is bool
            and isinstance(job.get("id"), str) and isinstance(job.get("username"), str)
            and _timestamp(job.get("created"))
            and _timestamp(job.get("updated", job["created"]))
            and _timestamp(job.get("expires", 0))
            and type(job.get("attempts", 0)) is int and job.get("attempts", 0) >= 0)


def get(job_id):
    if storage.store.backend == "memory":
        return (storage.store.get(ROOT) or {}).get(job_id)
    # Fetch only this job while streaming, not every queued job's checkpoint
    # index. Ownership transitions still use the shared dispatcher transaction.
    return storage.store.get(f"{ROOT}/{job_id}")


def reserve(job_id, username, scope, deep, owner, uid, guest_receipt_path=None):
    now = time.time()

    def change(current):
        current = current or {}
        if job_id in current:
            return current
        # Retain receipts separately from scan payloads. Expired jobs must not
        # execute again merely because a client replays an old request id.
        active = sum(not isinstance(j, dict) or not isinstance(j.get("status"), str)
                     or j["status"] not in TERMINAL
                     for j in current.values())
        if active >= config.SCAN_JOB_LIMIT or len(current) >= 256:
            raise Busy()
        current[job_id] = {"id": job_id, "username": username, "scope": scope,
                           "deep": deep, "owner": owner, "uid": uid,
                           "guest_receipt_path": guest_receipt_path,
                           "created": now, "updated": now, "status": "admitting",
                           "fingerprint": engine_fingerprint(scope, deep),
                           "checked": 0, "names": [], "refs": [], "attempts": 0}
        return current

    return storage.store.transaction(ROOT, change)[job_id]


def admit(job_id, charged):
    def change(current):
        job = current[job_id]
        if job["status"] == "admitting":
            job.update(status="queued", charged=charged, updated=time.time())
        return current
    return storage.store.transaction(ROOT, change)[job_id]


def reject(job_id):
    def change(current):
        if current and current.get(job_id, {}).get("status") == "admitting":
            current.pop(job_id, None)
        return current
    storage.store.transaction(ROOT, change)


def _lease(job, token):
    if (not job or job.get("token") != token or job.get("status") not in
            ("scanning", "finalizing") or job.get("expires", 0) <= time.time()):
        raise LostLease()


def claim(executor, versions=None):
    """Colab gets first chance; Render alone also performs finalization."""
    now = time.time()
    token = secrets.token_hex(24)
    selected = {}
    is_render = executor == "render"
    fingerprints = {}

    def current_fingerprint(job):
        key = job["scope"] + (":deep" if job["scope"] == "standard" and job["deep"] else "")
        if key not in fingerprints:
            fingerprints[key] = engine_fingerprint(job["scope"], job["deep"])
        return key, fingerprints[key]

    def change(current):
        selected.clear()
        current = current or {}
        entries = [job for job in current.values() if _dispatchable(job)]
        refreshed = False
        for job in entries:
            status = job.get("status")
            expired_scan = status == "scanning" and job.get("expires", 0) <= now
            if status != "queued" and not expired_scan:
                continue
            _, fingerprint = current_fingerprint(job)
            if job.get("fingerprint") == fingerprint:
                continue
            # An old catalogue/validator cannot safely share checkpoints with
            # the new implementation. Restart the already-admitted job only
            # after its old lease ends, preserving its billing receipt/owner.
            # Dropping the token fences any delayed writes from that worker.
            job.update(status="queued", fingerprint=fingerprint, checked=0,
                       names=[], refs=[], expires=0, updated=now,
                       revision_restarts=job.get("revision_restarts", 0) + 1,
                       worker_wait_until=now + config.SCAN_WORKER_WAIT_SECONDS)
            job.pop("token", None)
            job.pop("executor", None)
            refreshed = True
        # Only one Render job, including enrichment, regardless of HTTP
        # request count or how many processes accidentally start supervisors.
        if is_render and any(j.get("executor") == "render" and
                j.get("status") in ("scanning", "finalizing") and
                j.get("expires", 0) > now for j in entries):
            if refreshed:
                return current
            raise Abort()
        # Each external notebook runs at most one job at a time.
        if not is_render and any(j.get("executor") == executor and
                j.get("status") == "scanning" and j.get("expires", 0) > now
                for j in entries):
            if refreshed:
                return current
            raise Abort()
        # Completed worker batches free admission capacity only after Render
        # publishes their reports. Finish those before starting a potentially
        # long fallback scan, while preserving creation order within a phase.
        def priority(job):
            finalizable = job.get("status") == "raw_done" or (
                job.get("status") == "finalizing" and job.get("expires", 0) <= now)
            return (0 if is_render and finalizable else 1, job["created"])

        for job in sorted(entries, key=priority):
            status = job["status"]
            expired = status in ("scanning", "finalizing") and job.get("expires", 0) <= now
            finalize = status == "raw_done" or (expired and status == "finalizing")
            if finalize and not is_render:
                continue
            if not finalize and status != "queued" and not (expired and status == "scanning"):
                continue
            if not finalize and is_render and status == "queued" and (
                    now < job.get("worker_wait_until", 0) or (
                    now - job["updated"] < config.SCAN_WORKER_WAIT_SECONDS
                    and job.get("attempts", 0) < 2)):
                continue
            if not is_render:
                key, fingerprint = current_fingerprint(job)
                if (not versions or versions.get(key) != fingerprint
                        or job["fingerprint"] != fingerprint):
                    continue
            job.update(status="finalizing" if finalize else "scanning", executor=executor,
                       token=token, expires=now + config.SCAN_LEASE_SECONDS, updated=now,
                       attempts=job.get("attempts", 0) + 1)
            selected.update(job)
            return current
        # Persist revision reconciliation even when this particular notebook
        # has an obsolete bundle and therefore cannot claim any refreshed job.
        if refreshed:
            return current
        raise Abort()

    try:
        storage.store.transaction(ROOT, change)
    except Abort:
        return None
    return selected or None


def heartbeat(job_id, token):
    def change(current):
        job = (current or {}).get(job_id)
        _lease(job, token)
        job.update(expires=time.time() + config.SCAN_LEASE_SECONDS, updated=time.time())
        return current
    return storage.store.transaction(ROOT, change)[job_id]


def checkpoint(job_id, token, sequence, rows):
    job = get(job_id)
    _lease(job, token)
    clean = scan_engine.normalise(rows, job["username"], job["scope"], job["deep"])
    if not clean:
        return heartbeat(job_id, token)
    if type(sequence) is not int or not 0 <= sequence <= 10000:
        raise ValueError("Invalid checkpoint sequence")
    ref = f"{token}/{sequence}"
    digest = hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()
    existing = next((r for r in job.get("refs", []) if r["path"] == ref), None)
    if existing:
        if existing["digest"] != digest:
            raise ValueError("Checkpoint replay changed its contents")
        return heartbeat(job_id, token)
    # Immutable attempt path. Write before publish; never mutate a committed
    # checkpoint even if a response is lost and the client retries it.
    def immutable(old):
        if old is not None and old != clean:
            raise ValueError("Checkpoint replay changed its contents")
        return clean
    storage.store.transaction(f"{DATA}/{job_id}/chunks/{ref}", immutable)

    def change(current):
        entry = (current or {}).get(job_id)
        _lease(entry, token)
        prior = next((r for r in entry.get("refs", []) if r["path"] == ref), None)
        if prior:
            if prior["digest"] != digest:
                raise ValueError("Checkpoint replay changed its contents")
            return current
        names = [r["platform"] for r in clean]
        if set(names).intersection(entry.get("names", [])):
            raise ValueError("Platform already checkpointed")
        entry.setdefault("refs", []).append({"path": ref, "digest": digest})
        entry.setdefault("names", []).extend(names)
        entry.update(checked=len(entry["names"]), updated=time.time(),
                     expires=time.time() + config.SCAN_LEASE_SECONDS)
        return current
    return storage.store.transaction(ROOT, change)[job_id]


def raw_done(job_id, token):
    def change(current):
        job = (current or {}).get(job_id)
        _lease(job, token)
        expected = {p["name"] for p in scan_engine.catalogue(job["scope"], job["deep"])}
        if set(job.get("names", [])) != expected:
            raise ValueError("The worker has not checkpointed the complete catalogue")
        job.update(status="raw_done", updated=time.time(), expires=0)
        return current
    return storage.store.transaction(ROOT, change)[job_id]


def chunk(job_id, ref):
    value = storage.store.get(f"{DATA}/{job_id}/chunks/{ref['path']}")
    if (not isinstance(value, list) or hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
            != ref["digest"]):
        raise RuntimeError("A committed checkpoint is missing or corrupt")
    return value


def rows(job):
    out = []
    for ref in job.get("refs", []):
        out.extend(chunk(job["id"], ref))
    return out


def finish(job_id, token, data, history_id=None):
    job = get(job_id)
    _lease(job, token)
    storage.store.set(f"{DATA}/{job_id}/results/{token}", data)

    def change(current):
        entry = (current or {}).get(job_id)
        _lease(entry, token)
        entry.update(status="complete", result_token=token, history_id=history_id,
                     updated=time.time(), expires=0)
        entry.pop("names", None)
        return current
    return storage.store.transaction(ROOT, change)[job_id]


def fail(job_id, token=None, cancelled=False):
    def change(current):
        job = (current or {}).get(job_id)
        if not job or job["status"] in TERMINAL:
            raise Abort()
        if token is not None:
            _lease(job, token)
        job.update(status="cancelled" if cancelled else "failed", updated=time.time(), expires=0)
        return current
    try:
        return storage.store.transaction(ROOT, change)[job_id]
    except Abort:
        return get(job_id)


def expire(job_id, limit=3600, admitting=False):
    """Fail stale work only after rechecking its state/lease transactionally."""
    now = time.time()

    def change(current):
        job = (current or {}).get(job_id)
        if not job or job.get("status") in TERMINAL:
            raise Abort()
        if (job.get("status") == "admitting") != admitting:
            raise Abort()
        if job.get("status") in ("scanning", "finalizing") and job.get("expires", 0) > now:
            raise Abort()
        if now - job.get("updated", job["created"]) < limit:
            raise Abort()
        job.update(status="failed", updated=now, expires=0)
        return current

    try:
        return storage.store.transaction(ROOT, change)[job_id]
    except Abort:
        return get(job_id)


def release(job_id, token):
    """An external exception hands the same job to the bounded fallback."""
    def change(current):
        job = (current or {}).get(job_id)
        _lease(job, token)
        job.update(status="queued", attempts=max(2, job["attempts"]), updated=time.time(), expires=0)
        return current
    return storage.store.transaction(ROOT, change)[job_id]


def result(job):
    return storage.store.get(f"{DATA}/{job['id']}/results/{job['result_token']}")


def remember_history(job_id, result_token):
    def change(current):
        job = (current or {}).get(job_id)
        if not job or job["status"] != "complete" or job.get("result_token") != result_token:
            raise Abort()
        job["history_id"] = job_id
        return current
    try:
        storage.store.transaction(ROOT, change)
    except Abort:
        pass


def erase_history(uid, job_id=None):
    removed = []
    def change(current):
        removed.clear()
        for key, job in (current or {}).items():
            if (isinstance(job, dict) and job.get("uid") == uid
                    and isinstance(job.get("status"), str) and job["status"] in TERMINAL
                    and (job_id is None or key == job_id)):
                # Keep a small tombstone so replay cannot recreate a deleted
                # report using an already-spent admission receipt.
                current[key] = {"id": key, "uid": uid, "owner": job.get("owner", ""),
                    "created": job.get("created", time.time()), "updated": time.time(), "status": "deleted",
                    "checked": 0, "scope": job.get("scope", "standard"),
                    "deep": job.get("deep", False), "username": ""}
                removed.append(key)
        return current
    storage.store.transaction(ROOT, change)
    for key in removed:
        storage.store.delete(f"{DATA}/{key}")


def prune():
    now = time.time()
    removed = []

    def change(current):
        removed.clear()
        for key, job in list((current or {}).items()):
            if (isinstance(job, dict) and _timestamp(job.get("created"))
                    and now - job["created"] > config.SCAN_JOB_TTL_SECONDS
                    and isinstance(job.get("status"), str) and job["status"] in TERMINAL):
                current.pop(key)
                removed.append(key)
        return current
    storage.store.transaction(ROOT, change)
    for key in removed:
        storage.store.delete(f"{DATA}/{key}")
