"""Existing username API envelopes over persistent scan jobs; private worker API."""
import hashlib
import hmac
import json
import logging
import math
import re
import secrets
import threading
import time

from flask import Response, request, stream_with_context

import config
from core import plans, responses, scan_jobs as jobs, scan_workers as workers, validation, store as storage
from services import scan_engine, scan_job_runner

_ID = re.compile(r"^[a-f0-9]{32}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{16,80}$")
_wait_slots = threading.BoundedSemaphore(8)
log = logging.getLogger("myrecon.scan_workers")


def _waiting_response(response, release):
    original = response.response
    def wrapped():
        try:
            yield from original
        finally:
            release()
    response.response = wrapped()
    response.call_on_close(release)
    return response


def worker_authenticated():
    scheme, _, value = request.headers.get("Authorization", "").partition(" ")
    return (jobs.available() and scheme.lower() == "bearer" and bool(value)
            and hmac.compare_digest(value, config.SCAN_WORKER_TOKEN))


def worker_status_access():
    scheme, _, value = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not value:
        return "denied"
    return workers.status_access(value)


def worker_status_authenticated():
    return worker_status_access() == "allowed"


def _note_worker(callback, *args):
    """Presence telemetry must never discard an already valid job transition."""
    try:
        callback(*args)
        return True
    except Exception as exc:
        log.warning("Could not record scan-worker presence (%s)", type(exc).__name__)
        return False


def _operator_snapshot():
    """Aggregate queue health; never include job identities or finding data."""
    now = time.time()
    records = storage.store.get(jobs.ROOT) or {}
    active = [job for job in records.values() if isinstance(job, dict)
              and (not isinstance(job.get("status"), str) or job["status"] not in jobs.TERMINAL)]
    active_count = len(active) + sum(not isinstance(job, dict) for job in records.values())
    queued = [job for job in active if job.get("status") == "queued"]
    outdated = 0
    for job in queued:
        scope, deep = job.get("scope"), job.get("deep", False)
        if isinstance(scope, str) and scope in ("standard", "full", "extended") and type(deep) is bool:
            outdated += job.get("fingerprint") != jobs.engine_fingerprint(scope, deep)
    created = [job.get("created") for job in queued
               if type(job.get("created")) in (int, float) and math.isfinite(job["created"])]
    retained_limit = 256
    queue = {
        "capacity": config.SCAN_JOB_LIMIT,
        "active": active_count,
        "queued": len(queued),
        "scanning": sum(job.get("status") == "scanning" for job in active),
        "awaiting_finalization": sum(job.get("status") == "raw_done" for job in active),
        "finalizing": sum(job.get("status") == "finalizing" for job in active),
        "available_slots": max(0, min(config.SCAN_JOB_LIMIT - active_count, retained_limit - len(records))),
        "outdated_queued": outdated,
        "oldest_wait_seconds": max(0, int(now - min(created))) if created else 0,
        "retained_jobs": len(records),
        "retained_limit": retained_limit,
    }
    return {**workers.status(), "queue": queue}


def _owner(api):
    user = api._signed_in_user()
    identity = "user:" + user["sub"] if user else "guest:" + api._client_ip()
    owner = hmac.new(config.SECRET_KEY.encode(), identity.encode(), hashlib.sha256).hexdigest()
    return owner, user["sub"] if user else None


def _visible(api, job, data):
    return api._standard_response("username", data, job.get("uid"))


def handle(api, body, streaming):
    # Duplicate streams must not occupy every Gunicorn HTTP thread and
    # prevent the Colab heartbeat/claim requests that keep jobs alive.
    if not _wait_slots.acquire(blocking=False):
        return responses.error("Too many scan connections. Please try again shortly.", 429, "scan_connections_full")
    released, transferred = False, False
    lock = threading.Lock()
    def release():
        nonlocal released
        with lock:
            if not released:
                released = True
                _wait_slots.release()
    try:
        response = _handle(api, body, streaming)
        if isinstance(response, Response) and response.is_streamed:
            transferred = True
            return _waiting_response(response, release)
        return response
    finally:
        if not transferred:
            release()


def _handle(api, body, streaming):
    if not jobs.available():
        return responses.error("Scan workers require persistent storage and a dedicated worker token.",
                               status=503, code="scan_workers_unavailable")
    username = validation.username(body.get("username", ""))
    scope = api._scope(body)
    deep = validation.boolean(body.get("deep"))
    request_id = body.get("request_id") or secrets.token_hex(16)
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        raise validation.ValidationError("Invalid scan request id.")
    owner, uid = _owner(api)
    # Parameters are bound into the id: changing scope/user cannot reuse a
    # receipt to bypass payment or obtain another person's report.
    raw = json.dumps([owner, request_id, username, scope, deep])
    job_id = hmac.new(config.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    existing = jobs.get(job_id)
    if existing is None:
        from core import store as storage
        guest_path = plans.guest_job_path(api._client_ip()) if uid is None else None
        guest = storage.store.get(guest_path) if guest_path else None
        if (plans.job_receipt(uid, job_id) is not None or
                isinstance(guest, dict) and job_id in (guest.get("jobs") or {})):
            return responses.error("This scan request has expired. Start a new scan.",
                                   status=410, code="scan_request_expired")
        key = (api._cache_key("username_" + scope, username) if scope != "standard"
               else api._cache_key("username", username, deep))
        cached = api._cache.get(key) if config.CACHE_ENABLED else None
        if cached is not None:
            cached_uid, _ = api._admit_scan(scope, True)
            shown = api._standard_response("username", cached, cached_uid)
            history_id = api._remember(cached_uid, cached)
            if streaming:
                response = Response(json.dumps({"type": "complete", "data": shown,
                    "history_id": history_id}) + "\n", mimetype="application/x-ndjson")
                response.headers["Cache-Control"] = "no-store"
                return response
            return responses.ok({**shown, "history_id": history_id})
        try:
            existing = jobs.reserve(job_id, username, scope, deep, owner, uid, guest_path)
        except jobs.Busy:
            return responses.error("The scan queue is full. Please try again shortly.",
                                   status=429, code="scan_queue_full")
    if existing["status"] == "admitting":
        try:
            admitted_uid, charged = api._admit_scan(scope, False, job_id=job_id)
            if admitted_uid != uid:
                raise RuntimeError("Scan identity changed during admission")
            jobs.admit(job_id, charged)
        except (plans.NoAllowance, plans.StandardLimit, plans.GuestLimit,
                api.SignInRequired, api.AccountsUnavailable):
            jobs.reject(job_id)
            raise
        # A database write can fail after the allowance transaction committed.
        # Retain the admitting job so a retry or maintenance can recover it.
    scan_job_runner.ensure_started()
    if streaming:
        response = Response(stream_with_context(events(api, job_id)), mimetype="application/x-ndjson")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Accel-Buffering"] = "no"
        return response
    # JSON callers still use the same endpoint; durable status is available
    # separately if their network request ends before the worker finishes.
    for event in events(api, job_id):
        value = json.loads(event)
        if value["type"] == "complete":
            return responses.ok({**value["data"], "history_id": value.get("history_id"),
                                 "job_id": job_id})
        if value["type"] == "error":
            return responses.error(value["error"], status=503, code="scan_failed")


def events(api, job_id):
    yield json.dumps({"type": "job", "job_id": job_id, "resumable": True}) + "\n"
    seen = set()
    while True:
        job = jobs.get(job_id)
        if not job:
            yield json.dumps({"type": "error", "error": "This saved scan job has expired."}) + "\n"
            return
        if job["status"] == "complete":
            data = jobs.result(job)
            if not isinstance(data, dict):
                raise RuntimeError("Completed scan result is missing")
            yield json.dumps({"type": "complete", "data": _visible(api, job, data),
                              "history_id": job.get("history_id"), "job_id": job_id}) + "\n"
            return
        if job["status"] in ("failed", "cancelled", "deleted"):
            scan_job_runner.refund(job)
            yield json.dumps({"type": "error", "error": "The scan was cancelled." if
                              job["status"] == "cancelled" else "This saved scan was deleted." if
                              job["status"] == "deleted" else "The scan could not complete. Please try again."}) + "\n"
            return
        total = len(scan_engine.catalogue(job["scope"], job["deep"]))
        phase = "Preparing results" if job["status"] in ("raw_done", "finalizing") else (
            "Queued" if job["status"] in ("queued", "admitting") else "Checking platforms")
        event = {"type": "progress", "phase": phase,
                 "percent": 70 if phase == "Preparing results" else max(1, int(job["checked"] / total * 68)),
                 "detail": f"Checked {job['checked']} of {total} platforms."}
        yield json.dumps(event) + "\n"
        from services.search import _live_view
        for ref in job.get("refs", []):
            if ref["path"] in seen:
                continue
            seen.add(ref["path"])
            for row in jobs.chunk(job_id, ref):
                # Guest finding details are withheld until final card order is
                # known. Arrival-order rows would expose additional locked
                # cards after the final report sorts its first two findings.
                if row.get("exists") and job.get("uid"):
                    yield json.dumps({"type": "found", "result": _live_view(row, job["username"])}) + "\n"
        time.sleep(3)


def register(app, api):
    def owned(job_id):
        if not _ID.fullmatch(job_id):
            return None
        job = jobs.get(job_id)
        owner, _ = _owner(api)
        return job if job and hmac.compare_digest(job["owner"], owner) else None

    @app.route("/api/username/jobs/<job_id>", methods=["GET", "DELETE"])
    def job_status(job_id):
        if not jobs.available():
            return responses.error("Scan workers are disabled.", 404)
        job = owned(job_id)
        if not job:
            return responses.error("Scan job not found.", 404)
        scan_job_runner.ensure_started()
        if request.method == "DELETE":
            job = jobs.fail(job_id, cancelled=True)
            scan_job_runner.refund(job)
        payload = {"job_id": job_id, "job_status": job["status"], "checked": job["checked"]}
        if job["status"] == "complete":
            payload.update(data=_visible(api, job, jobs.result(job)), history_id=job.get("history_id"))
        response, status = responses.ok(payload)
        response.headers["Cache-Control"] = "no-store"
        return response, status

    @app.route("/api/username/jobs/<job_id>/stream")
    def job_stream(job_id):
        if not jobs.available() or not owned(job_id):
            return responses.error("Scan job not found.", 404)
        scan_job_runner.ensure_started()
        if not _wait_slots.acquire(blocking=False):
            return responses.error("Too many scan connections. Please try again shortly.", 429, "scan_connections_full")
        released = False
        lock = threading.Lock()
        def release():
            nonlocal released
            with lock:
                if not released:
                    released = True
                    _wait_slots.release()
        response = Response(stream_with_context(events(api, job_id)), mimetype="application/x-ndjson")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Accel-Buffering"] = "no"
        return _waiting_response(response, release)

    @app.route("/api/scan-worker/<action>", methods=["POST"])
    def worker(action):
        if not worker_authenticated():
            return responses.error("Worker authentication failed.", 401)
        api._require_json_content_type()
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return responses.error("Invalid worker payload.", 422)
        scan_job_runner.ensure_started()
        try:
            if action == "claim":
                worker_id = body.get("worker_id", "")
                workers.validate_worker_id(worker_id)
                worker_label = workers.validate_label(body.get("worker_label"))
                versions = body.get("catalogues")
                if not isinstance(versions, dict) or body.get("protocol") != scan_engine.PROTOCOL:
                    raise ValueError("Worker protocol mismatch")
                job = jobs.claim("colab:" + worker_id, versions)
                presence_recorded = _note_worker(workers.seen_claim, worker_id, worker_label, job, versions)
                if not job:
                    return responses.ok({"job": None, "presence_recorded": presence_recorded})
                # Deliberately excludes uid, owner, billing receipts and RTDB paths.
                payload = {key: job[key] for key in ("id", "username", "scope", "deep",
                           "token", "fingerprint")}
                # Firebase removes empty lists from stored objects.
                payload["names"] = job.get("names", [])
                payload["lease_seconds"] = config.SCAN_LEASE_SECONDS
                return responses.ok({"job": payload, "presence_recorded": presence_recorded})
            if action == "stopped":
                worker_id = workers.validate_worker_id(body.get("worker_id", ""))
                return responses.ok({"accepted": True,
                                     "presence_recorded": _note_worker(workers.stopped, worker_id)})
            job_id, token = body.get("job_id", ""), body.get("lease_token", "")
            if not isinstance(job_id, str) or not _ID.fullmatch(job_id) or not isinstance(token, str):
                raise ValueError("Invalid lease")
            presence_recorded = True
            if action == "heartbeat":
                job = jobs.heartbeat(job_id, token)
                worker_id = workers.worker_id_for(job)
                if worker_id:
                    presence_recorded = _note_worker(workers.seen_busy, worker_id)
            elif action == "checkpoint":
                job = jobs.checkpoint(job_id, token, body.get("sequence"), body.get("rows"))
                worker_id = workers.worker_id_for(job)
                if worker_id:
                    presence_recorded = _note_worker(workers.seen_busy, worker_id)
            elif action == "complete":
                job = jobs.raw_done(job_id, token)
                worker_id = workers.worker_id_for(job)
                if worker_id:
                    presence_recorded = _note_worker(workers.seen_recovering, worker_id)
            elif action == "release":
                job = jobs.release(job_id, token)
                worker_id = workers.worker_id_for(job)
                if worker_id:
                    presence_recorded = _note_worker(workers.seen_recovering, worker_id)
            else:
                return responses.error("Worker endpoint not found.", 404)
            return responses.ok({"accepted": True, "presence_recorded": presence_recorded})
        except jobs.LostLease:
            return responses.error("This scan lease has expired or was cancelled.", 409, "lost_lease")
        except (ValueError, TypeError):
            return responses.error("Invalid worker payload or catalogue version.", 422)

    @app.route("/api/operator/scan-workers")
    def worker_status():
        """Token-only status for the owner Apps Script health monitor."""
        access = worker_status_access()
        if access == "unconfigured":
            return responses.error("Worker status monitoring is not configured.", 503,
                                   "worker_status_unconfigured")
        if access != "allowed":
            return responses.error("Operator authentication failed.", 401)
        response, status = responses.ok(_operator_snapshot())
        response.headers["Cache-Control"] = "no-store"
        return response, status

    @app.route("/api/operator/worker-console")
    def worker_console():
        """Firebase-authenticated snapshot for the installed owner PWA."""
        user = api._require_user()
        access = workers.operator_access(user)
        if access == "unconfigured":
            return responses.error("Worker console access is not configured on Render.", 503,
                                   "worker_console_unconfigured")
        if access != "allowed":
            return responses.error("This Google account is not allowed to use the private worker console.", 403,
                                   "worker_console_not_owner")
        response, status = responses.ok({**_operator_snapshot(), "launcher_url": workers.launcher_url()})
        response.headers["Cache-Control"] = "no-store"
        return response, status
