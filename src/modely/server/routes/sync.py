"""Sync route adapters for Phase 1b enterprise API."""

from __future__ import annotations

from ..schemas.sync import SyncJobLogResponse, SyncJobResponse
from ..schemas.envelopes import error_response, success_response


def _extract(payload: dict, key: str) -> str:
    """Get a value from *payload*, also checking nested body when FastAPI
    unpacks POST fields into ``payload["payload"][key]``."""
    val = payload.get(key, "")
    if not val and "payload" in payload:
        inner = payload.get("payload", {})
        if isinstance(inner, dict):
            val = inner.get(key, "")
    return str(val).strip()


def list_sync_jobs(service, *, request_id: str = "req_unknown") -> dict:
    """List all sync jobs. GET /api/v1/sync-jobs"""
    raw = service.list_sync_jobs()
    jobs = [_job_to_response(j) for j in raw]
    return success_response({"jobs": jobs, "total": len(jobs)}, request_id=request_id)


def create_sync_job(service, *, request_id: str = "req_unknown", sync_worker: Any | None = None, _method: str = "", **payload: str) -> dict:
    """Create a sync job (POST) or list all sync jobs (GET).

    When ``_method`` is ``"GET"`` (injected by the FastAPI adapter) or no
    ``target_id`` is present in the body, returns the job list.
    When ``_method`` is ``"POST"`` or ``target_id`` is provided, creates a job.
    """

    # Collect body params from both direct kwargs (test mode) and payload dict (FastAPI mode)
    target_id = _extract(payload, "target_id")
    resource = _extract(payload, "resource")

    # GET: list all sync jobs (explicit GET or no target_id)
    if _method == "GET" or (not target_id and _method != "POST"):
        raw = service.list_sync_jobs()
        jobs = [_job_to_response(j) for j in raw]
        return success_response({"jobs": jobs, "total": len(jobs)}, request_id=request_id)

    # POST: create a sync job
    from ...syncing.workers import LocalMirrorWorker
    if not resource:
        return error_response("validation_error", "Missing required field: resource", request_id=request_id, details={"field": "resource"})

    # idempotency conflict detection — check BEFORE creating
    idempotency_key = _extract(payload, "idempotency_key")
    if idempotency_key and hasattr(service, "find_job_by_idempotency_key"):
        existing = service.find_job_by_idempotency_key(idempotency_key)
        if existing is not None:
            existing_dict = existing.to_dict() if hasattr(existing, "to_dict") else dict(existing)
            return error_response(
                "conflict_idempotency",
                f"Sync job with idempotency key '{idempotency_key}' already exists.",
                request_id=request_id,
                details={"existing_job_id": existing_dict.get("id", ""), "existing_status": existing_dict.get("status", "")},
            )

    try:
        job = service.create_sync_job(**payload)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    # ── Synchronous execution via injected worker ─────────────────────────
    worker_result = None
    if sync_worker is not None and isinstance(sync_worker, LocalMirrorWorker):
        try:
            worker_result = sync_worker.run(job)
        except Exception as exc:
            worker_result = {"status": "failed", "error": str(exc)}

    job_dict = job.to_dict() if hasattr(job, "to_dict") else dict(job)

    job_response = SyncJobResponse(
        id=job_dict.get("id", ""),
        target_id=job_dict.get("target_id", target_id),
        resource=job_dict.get("resource", resource),
        status=job_dict.get("status", "registered"),
        action=job_dict.get("action", "sync"),
        attempts=job_dict.get("attempts", 0),
        error=job_dict.get("error"),
        created_at=job_dict.get("created_at"),
        updated_at=job_dict.get("updated_at"),
        metadata=dict(job_dict.get("metadata", {})),
    )
    result = success_response(job_response.to_dict(), request_id=request_id)
    if worker_result is not None:
        result["worker"] = worker_result.to_dict() if hasattr(worker_result, "to_dict") else dict(worker_result)
    return result


def get_sync_job(service, job_id: str, *, request_id: str = "req_unknown") -> dict:
    """Return sync job status, wrapped in the API response envelope.

    Returns a ``not_found`` error envelope when the job is absent.
    """

    job = service.get_sync_job(job_id)
    if job is None:
        return error_response("not_found", f"Sync job not found: {job_id}", request_id=request_id)

    job_dict = job.to_dict() if hasattr(job, "to_dict") else dict(job)
    identity = job_dict.get("identity", {})
    job_response = SyncJobResponse(
        id=job_dict.get("id", job_id),
        target_id=job_dict.get("target_id", identity.get("target_id", "")),
        resource=job_dict.get("resource", identity.get("resource", "")),
        status=job_dict.get("status", "unknown"),
        action=job_dict.get("action", "sync"),
        attempts=job_dict.get("attempts", 0),
        error=job_dict.get("error"),
        created_at=job_dict.get("created_at"),
        updated_at=job_dict.get("updated_at"),
        metadata=dict(job_dict.get("metadata", {})),
    )
    return success_response(job_response.to_dict(), request_id=request_id)


def get_sync_job_logs(service, job_id: str, *, request_id: str = "req_unknown") -> dict:
    """Return sync job logs or an empty log response, wrapped in the API envelope.

    Returns a ``not_found`` error envelope when the job is absent.
    """

    job = service.get_sync_job(job_id)
    if job is None:
        return error_response("not_found", f"Sync job not found: {job_id}", request_id=request_id)

    job_dict = job.to_dict() if hasattr(job, "to_dict") else dict(job)
    meta = job_dict.get("metadata", {})
    result = meta.get("result", {})
    events: list = []

    if isinstance(result, dict):
        # Build structured events from the worker result
        now_iso = job_dict.get("updated_at") or job_dict.get("created_at") or ""

        # 1. Job lifecycle event
        events.append({
            "timestamp": now_iso,
            "event": job_dict.get("status", "unknown"),
            "job_id": job_id,
            "attempt": job_dict.get("attempts", 0),
        })

        # 2. Error event (when failed)
        error_msg = job_dict.get("error") or result.get("error")
        if error_msg:
            events.append({
                "timestamp": now_iso,
                "event": "error",
                "message": error_msg,
                "source": "worker_result" if result.get("error") else "job",
            })

        # 3. Asset info (when synced)
        if result.get("asset_id"):
            events.append({
                "timestamp": now_iso,
                "event": "asset_created",
                "asset_id": result.get("asset_id"),
                "version_id": result.get("version_id"),
                "file_count": len(result.get("files", [])),
            })

        # 4. File-level events (when files were downloaded)
        for f in result.get("files", []) or []:
            events.append({
                "timestamp": now_iso,
                "event": "file_downloaded",
                "path": f.get("path", ""),
                "size": f.get("size", 0),
                "uri": f.get("uri") or f.get("local_path") or "",
            })

    log_response = SyncJobLogResponse(
        job_id=job_id,
        status=job_dict.get("status", "unknown"),
        events=events,
        error=job_dict.get("error") or result.get("error") if isinstance(result, dict) else job_dict.get("error"),
        metadata={"source": "job_metadata", "diagnostic_mode": True},
    )
    return success_response(log_response.to_dict(), request_id=request_id)


def _job_to_response(job_dict: dict) -> dict:
    """Normalize a job dict/DTO into a SyncJobResponse dict."""
    d = job_dict.to_dict() if hasattr(job_dict, "to_dict") else dict(job_dict)
    identity = d.get("identity", {})
    return SyncJobResponse(
        id=d.get("id", ""),
        target_id=d.get("target_id", identity.get("target_id", "")),
        resource=d.get("resource", identity.get("resource", "")),
        status=d.get("status", "unknown"),
        action=d.get("action", "sync"),
        attempts=d.get("attempts", 0),
        error=d.get("error"),
        created_at=d.get("created_at"),
        updated_at=d.get("updated_at"),
        metadata=dict(d.get("metadata", {})),
    ).to_dict()


__all__ = ["create_sync_job", "get_sync_job", "get_sync_job_logs", "list_sync_jobs"]
