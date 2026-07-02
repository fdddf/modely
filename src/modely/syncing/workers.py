"""Sync worker orchestration entry points."""

from __future__ import annotations

import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from ..application.file_queries import filter_files
from ..cataloging.repository import LocalMirrorRepository
from ..domain.approvals import ApprovalRequest
from ..domain.assets import Asset, AssetIdentity
from ..domain.files import AssetFile, AssetFileIdentity
from ..domain.versions import AssetVersion, AssetVersionIdentity
from ..storage.base import StoredObject, StorageBackend
from ..types import DownloadManifest, FileInfo
from ..uri import parse_modely_uri
from .adapters import SourceAdapter
from .jobs import SyncJob
from .manifests import create_storage_manifest


@dataclass
class LocalSyncResult:
    """Result of one synchronous local mirror worker run."""

    job_id: str
    status: str
    asset_id: str | None = None
    version_id: str | None = None
    local_path: str | None = None
    manifest_path: str | None = None
    manifest: dict[str, Any] | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalMirrorWorker:
    """Minimal synchronous local mirror worker for Phase 1a."""

    def __init__(self, *, adapter: SourceAdapter, storage: StorageBackend, repository: LocalMirrorRepository | None = None):
        self.adapter = adapter
        self.storage = storage
        self.repository = repository

    def run(self, job: SyncJob) -> LocalSyncResult:
        """Run one local mirror sync job synchronously."""

        job.attempts += 1
        job.status = "syncing"
        job.error = None
        try:
            result = self._run(job)
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            result = LocalSyncResult(job_id=job.id, status="failed", error=str(exc))
            job.metadata["result"] = result.to_dict()
            self._save_job(job)
            return result
        job.status = "synced"
        job.metadata["result"] = result.to_dict()
        self._save_job(job)
        return result

    def _run(self, job: SyncJob) -> LocalSyncResult:
        resource = job.identity.resource
        if not resource:
            raise ValueError("Sync job requires identity.resource")
        ref = parse_modely_uri(resource)
        revision = job.identity.revision or self.adapter.resolve_revision(ref) or ref.revision or "fixture"
        ref.revision = revision
        include = job.metadata.get("include")
        exclude = job.metadata.get("exclude")
        checksum = bool(job.metadata.get("checksum", True))
        try:
            raw_files = self.adapter.list_files(ref)
        except Exception as exc:
            raise ValueError(f"Failed to list files for {resource} (revision: {revision}): {exc}") from exc
        if not raw_files:
            raise ValueError(
                f"No files found for {resource} (revision: {revision}). "
                f"The revision may not exist, or the repository may be empty."
            )
        selected_files = filter_files(raw_files, include, exclude)
        if not selected_files:
            pattern_info = ""
            if include:
                pattern_info += f" include={include}"
            if exclude:
                pattern_info += f" exclude={exclude}"
            raise ValueError(
                f"No files matched filter patterns for {resource} (revision: {revision}). "
                f"Found {len(raw_files)} remote file(s) but all were filtered out.{pattern_info}"
            )
        asset_id = _asset_id(ref.source, ref.repo_type, ref.repo_id)
        version_id = _version_id(asset_id, revision, job.identity.idempotency_key or job.id)
        stored_for_manifest: list[StoredObject] = []
        asset_files: list[AssetFile] = []
        with tempfile.TemporaryDirectory(prefix=f"modely-{job.id}-") as tmp_dir:
            tmp_root = Path(tmp_dir)
            for file_info in selected_files:
                downloaded = self.adapter.download_file(ref, file_info, tmp_root)
                storage_key = _storage_key(ref.source, ref.repo_type, ref.repo_id, revision, file_info.path)
                stored = self.storage.put_file(storage_key, downloaded, metadata={"source_path": file_info.path, "job_id": job.id})
                stored_for_manifest.append(
                    StoredObject(
                        key=file_info.path,
                        size=stored.size,
                        sha256=stored.sha256 if checksum else None,
                        uri=stored.key,
                        metadata={"storage_key": stored.key, "job_id": job.id},
                    )
                )
                asset_files.append(
                    AssetFile(
                        id=_file_id(version_id, file_info.path),
                        identity=AssetFileIdentity(asset_id=asset_id, version_id=version_id, revision=revision, path=file_info.path),
                        path=file_info.path,
                        size=stored.size,
                        sha256=stored.sha256 if checksum else None,
                        local_path=stored.uri,
                        download_url=stored.uri,
                        metadata={"storage_key": stored.key},
                    )
                )
        manifest_output = job.metadata.get("manifest_path")
        manifest = create_storage_manifest(
            resource,
            stored_for_manifest,
            storage_root=job.metadata.get("storage_root", "local-storage"),
            output=manifest_output,
            metadata={"job_id": job.id, "asset_id": asset_id, "version_id": version_id, "include": include, "exclude": exclude},
        )
        asset = Asset(
            id=asset_id,
            identity=AssetIdentity(source=ref.source, repo_type=ref.repo_type, repo_id=ref.repo_id, revision=revision),
            source_url=resource,
            size=sum(file.size for file in asset_files),
            file_count=len(asset_files),
            checksum=_version_checksum(manifest),
            operational_state="synced",
            metadata={"job_id": job.id, "manifest": manifest.to_dict()},
        )
        version = AssetVersion(
            id=version_id,
            asset_id=asset_id,
            identity=AssetVersionIdentity(asset_id=asset_id, revision=revision, source=ref.source, repo_id=ref.repo_id),
            revision=revision,
            size=asset.size,
            file_count=asset.file_count,
            checksum=asset.checksum,
            metadata={"job_id": job.id, "manifest": manifest.to_dict()},
        )
        if self.repository is not None:
            self.repository.assets.save_asset(asset)
            self.repository.versions.save_version(version)
            for asset_file in asset_files:
                self.repository.files.save_file(asset_file)
        return LocalSyncResult(
            job_id=job.id,
            status="synced",
            asset_id=asset_id,
            version_id=version_id,
            local_path=job.metadata.get("local_dir"),
            manifest_path=str(manifest_output) if manifest_output else None,
            manifest=manifest.to_dict(),
            files=[file.to_dict() for file in asset_files],
            metadata={"asset": asset.to_dict(), "version": version.to_dict()},
        )

    def _save_job(self, job: SyncJob) -> None:
        jobs = getattr(self.repository, "jobs", None)
        if jobs is not None:
            jobs.save_job(job)


def run_local_mirror_job(
    job: SyncJob,
    *,
    adapter: SourceAdapter,
    storage: StorageBackend,
    repository: LocalMirrorRepository | None = None,
) -> LocalSyncResult:
    """Run one local mirror sync job with injected dependencies."""

    return LocalMirrorWorker(adapter=adapter, storage=storage, repository=repository).run(job)


def run_sync_job(job: SyncJob, handler: Callable[[SyncJob], Any]) -> SyncJob:
    """Execute a sync job through an injected handler and update job metadata.

    Server routes should create/return job contracts; actual work belongs in worker
    orchestration like this function or a future queue-backed runner.
    """

    try:
        result = handler(job)
        job.status = "synced"
        job.metadata["result"] = result.to_dict() if hasattr(result, "to_dict") else result
    except Exception as exc:  # pragma: no cover - exercised by callers with concrete handlers
        job.status = "failed"
        job.error = str(exc)
    finally:
        job.attempts += 1
    return job


def _asset_id(source: str, repo_type: str, repo_id: str) -> str:
    return f"{source}:{repo_type}:{repo_id.replace('/', '--')}"


def _version_id(asset_id: str, revision: str | None, idempotency_key: str | None) -> str:
    return f"{asset_id}:{(revision or 'unknown').replace('/', '--')}:{idempotency_key or 'default'}"


def _file_id(version_id: str, path: str) -> str:
    return f"{version_id}:{path.replace('/', '--')}"


def _storage_key(source: str, repo_type: str, repo_id: str, revision: str | None, path: str) -> str:
    safe_repo = repo_id.replace("/", "--")
    safe_revision = (revision or "unknown").replace("/", "--")
    return f"assets/{source}/{repo_type}/{safe_repo}/{safe_revision}/{path}"


def _version_checksum(manifest: DownloadManifest) -> str | None:
    checksums = [file.sha256 for file in manifest.files if file.sha256]
    if not checksums:
        return None
    return ";".join(checksums)


# ---------------------------------------------------------------------------
# Approval expiry worker (Phase 2 step 3)
# ---------------------------------------------------------------------------


@dataclass
class ApprovalExpiryResult:
    """Result of one approval expiry worker invocation."""

    expired_count: int = 0
    escalated_count: int = 0
    reminded_count: int = 0
    error_count: int = 0
    error_messages: list[str] = field(default_factory=list)
    expired_request_ids: list[str] = field(default_factory=list)
    escalated_request_ids: list[str] = field(default_factory=list)
    reminded_request_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_approval_expiry_worker(
    requests: Sequence[ApprovalRequest],
    *,
    now: str | None = None,
    escalation_targets: dict[str, str] | None = None,
    hooks: Any = None,
) -> ApprovalExpiryResult:
    """Approval expiry worker: expire overdue requests and trigger escalation.

    This worker iterates over approval requests in non-terminal states,
    checks SLA and approval expiry, and emits audit events for each action.

    Workflow:
    1. Identify non-terminal requests (``pending``, ``approved`` states that
       have not yet reached ``expired``, ``rejected``, ``cancelled``).
    2. For each pending request past its ``sla_target``: transition to
       ``expired``.
    3. For each approved request past its ``expires_at``: transition to
       ``expired``.
    4. For pending requests within the reminder window: trigger ``on_reminder``
       hook (when a ``NotificationHook`` is provided via *hooks*).
    5. For pending requests past SLA that have an escalation target in
       *escalation_targets*: call ``escalate_overdue`` and invoke
       ``hooks.on_escalation``.

    Safety invariants:
    - This worker NEVER auto-approves.  The only state transition it
      performs is ``pending`` / ``approved`` -> ``expired``.
    - Escalation is about notification, not authorization.  It does not
      change the approval state.

    Args:
        requests: Approval requests to evaluate.
        now: Optional ISO-8601 timestamp to use as "now" (default: current UTC).
        escalation_targets: Optional mapping of ``request_id -> escalation_target``
            (principal or team id) for requests that should be escalated when
            overdue.
        hooks: Optional ``NotificationHook`` instance for reminder/escalation
            callbacks.

    Returns:
        ``ApprovalExpiryResult`` summarizing the actions taken.
    """
    from ..domain.approvals import ApprovalRequest, SLA_REMINDER_INTERVAL_HOURS
    from ..governance.approvals import (
        NotificationHook,
        escalate_overdue,
        transition_request,
    )

    if now is None:
        now_dt = datetime.now(timezone.utc)
    else:
        now_dt = datetime.fromisoformat(now)

    escalation_targets = escalation_targets or {}

    result = ApprovalExpiryResult()

    for req in requests:
        # Only process non-terminal states
        if req.state not in {"pending", "approved"}:
            continue

        try:
            # ── Pending requests: check SLA and reminder windows ──────────
            if req.state == "pending" and req.sla_target:
                try:
                    sla_dt = datetime.fromisoformat(req.sla_target.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    result.error_count += 1
                    result.error_messages.append(
                        f"Invalid sla_target for request {req.id}: {req.sla_target}"
                    )
                    continue

                # Check reminder threshold
                reminder_dt = sla_dt - timedelta(hours=SLA_REMINDER_INTERVAL_HOURS)
                if now_dt >= reminder_dt and now_dt < sla_dt:
                    if req.notification_state == "pending":
                        req.notification_state = "sent"
                        result.reminded_count += 1
                        result.reminded_request_ids.append(req.id)
                        if hooks is not None and isinstance(hooks, NotificationHook):
                            hooks.on_reminder(req)

                # SLA breach: expire the request
                if now_dt > sla_dt:
                    # Escalate before expiring if escalation target is set
                    escalation_target = escalation_targets.get(req.id)
                    if escalation_target:
                        escalate_overdue(req, escalation_target, reason="SLA timeout — auto-escalated")
                        result.escalated_count += 1
                        result.escalated_request_ids.append(req.id)
                        if hooks is not None and isinstance(hooks, NotificationHook):
                            hooks.on_escalation(req, escalation_target)

                    transition_request(
                        req, "expired", reason="SLA timeout — auto-expired by expiry worker"
                    )
                    result.expired_count += 1
                    result.expired_request_ids.append(req.id)

            # ── Approved requests: check approval expiry ──────────────────
            elif req.state == "approved" and req.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(req.expires_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    result.error_count += 1
                    result.error_messages.append(
                        f"Invalid expires_at for request {req.id}: {req.expires_at}"
                    )
                    continue

                if now_dt > exp_dt:
                    transition_request(
                        req, "expired", reason="Approval validity period expired — auto-expired by expiry worker"
                    )
                    result.expired_count += 1
                    result.expired_request_ids.append(req.id)

        except ValueError as exc:
            result.error_count += 1
            result.error_messages.append(f"Error processing request {req.id}: {exc}")

    return result


__all__ = [
    "ApprovalExpiryResult",
    "LocalMirrorWorker",
    "LocalSyncResult",
    "main",
    "run_approval_expiry_worker",
    "run_local_mirror_job",
    "run_sync_job",
    "WorkerRunLoop",
]


# ---------------------------------------------------------------------------
# Worker run loop — async job consumer
# ---------------------------------------------------------------------------


class WorkerRunLoop:
    """Poll-based worker that consumes jobs from a repository.

    Designed for single-node / dev deployments without a message queue.
    Upgrade to RQ/Celery for production-scale workloads.

    Usage::

        loop = WorkerRunLoop(adapter=adapter, storage=storage, repository=repo)
        loop.run_once()       # Fetch and execute one batch
        loop.run_forever()    # Continuous polling loop (Ctrl+C to stop)
    """

    def __init__(
        self,
        *,
        adapter: SourceAdapter,
        storage: StorageBackend,
        repository: LocalMirrorRepository | None = None,
        poll_interval: float = 5.0,
        max_jobs_per_tick: int = 1,
    ):
        self._worker = LocalMirrorWorker(adapter=adapter, storage=storage, repository=repository)
        self._repository = repository
        self.poll_interval = poll_interval
        self.max_jobs_per_tick = max_jobs_per_tick
        self._running = False

    def run_once(self) -> dict[str, Any]:
        """Fetch planned jobs from the repository and execute them.

        Returns a summary dict with counts of jobs processed.
        """
        planned = self._fetch_planned_jobs()
        results = []
        for job in planned:
            result = self._worker.run(job)
            results.append({"job_id": job.id, "status": result.status, "error": result.error})
        summary = {
            "planned_count": len(planned),
            "executed_count": len(results),
            "results": results,
        }
        return summary

    def run_forever(self) -> None:
        """Continuously poll for jobs.  Press Ctrl+C to stop."""
        import time

        self._running = True
        print(f"Worker running: poll_interval={self.poll_interval}s, max_jobs={self.max_jobs_per_tick}")
        try:
            while self._running:
                summary = self.run_once()
                if summary["executed_count"] > 0:
                    statuses = ", ".join(f"{r['job_id']}:{r['status']}" for r in summary["results"])
                    print(f"executed {summary['executed_count']} job(s): {statuses}")
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\nWorker stopped.")

    def stop(self) -> None:
        """Signal the run loop to stop after the current tick."""
        self._running = False

    def _fetch_planned_jobs(self) -> list[SyncJob]:
        if self._repository is None or not hasattr(self._repository, "jobs"):
            return []
        jobs_repo = self._repository.jobs
        planned = []
        try:
            all_jobs = jobs_repo.list_jobs() if hasattr(jobs_repo, "list_jobs") else []
            for j in all_jobs:
                status = j.status if hasattr(j, "status") else j.get("status", "")
                if status in ("planned", "queued", "registered"):
                    planned.append(j)
                    if len(planned) >= self.max_jobs_per_tick:
                        break
        except Exception:
            pass
        return planned


# ---------------------------------------------------------------------------
# CLI entry point (modely-worker)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """``modely-worker`` entry point.

    Usage::

        modely-worker run      # Run async job consumer loop (poll-based)
        modely-worker sync     # Run a local mirror sync (fixture-based)
        modely-worker expire   # Run approval expiry worker
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="modely-worker",
        description="modely enterprise worker — sync, scan, approval expiry, and report jobs",
    )
    sub = parser.add_subparsers(dest="command", help="Worker command")

    # -- run (async loop) ----------------------------------------------------
    run_parser = sub.add_parser("run", help="Run worker consumer loop (poll-based queue)")
    run_parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds (default: 5)")
    run_parser.add_argument("--max-jobs", type=int, default=1, help="Max jobs per tick (default: 1)")
    run_parser.add_argument("--once", action="store_true", help="Run one tick and exit (no loop)")
    run_parser.add_argument("--resource", default=None, help="modely URI (for single-job mode)")
    run_parser.add_argument("--root", default=None, help="Fixture adapter root directory")

    # -- sync ---------------------------------------------------------------
    sync_parser = sub.add_parser("sync", help="Run a local mirror sync worker")
    sync_parser.add_argument("--resource", required=True, help="modely URI to sync")
    sync_parser.add_argument("--revision", default=None, help="Revision to pin")
    sync_parser.add_argument("--job-id", default=None, help="Sync job id (generated if omitted)")
    sync_parser.add_argument("--idempotency-key", default=None, help="Idempotency key for the run")
    sync_parser.add_argument("--include", nargs="+", default=None, help="File patterns to include")
    sync_parser.add_argument("--exclude", nargs="+", default=None, help="File patterns to exclude")
    sync_parser.add_argument("--checksum", action="store_true", default=True, help="Enable SHA256 checksums")
    sync_parser.add_argument("--dry-run", action="store_true", help="Plan only, do not execute")

    # -- expire -------------------------------------------------------------
    expire_parser = sub.add_parser("expire", help="Run approval expiry worker")
    expire_parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")

    args = parser.parse_args(argv)

    if args.command == "run":
        _run_loop_command(args)
    elif args.command == "sync":
        _run_sync_command(args)
    elif args.command == "expire":
        _run_expire_command(args)
    else:
        parser.print_help()


def _run_loop_command(args: Any) -> None:
    """Execute the ``run`` sub-command — async job consumer loop."""
    import tempfile
    from pathlib import Path

    from ..storage.local import LocalStorageBackend
    from .adapters import FixtureSourceAdapter

    root = args.root or tempfile.mkdtemp(prefix="modely-worker-")
    Path(root).mkdir(parents=True, exist_ok=True)

    adapter = FixtureSourceAdapter(root=root)
    storage = LocalStorageBackend(root=root)

    loop = WorkerRunLoop(
        adapter=adapter,
        storage=storage,
        poll_interval=args.interval,
        max_jobs_per_tick=args.max_jobs,
    )

    if args.once:
        summary = loop.run_once()
        print(f"Tick complete: {summary['executed_count']} job(s) executed")
    else:
        loop.run_forever()


def _run_sync_command(args: Any) -> None:
    """Execute the ``sync`` sub-command."""
    import uuid

    from ..application.download_profiles import PROFILES
    from ..storage.local import LocalStorageBackend
    from .adapters import FixtureSourceAdapter
    from .jobs import SyncJob, SyncJobIdentity

    resource = args.resource
    job_id = args.job_id or f"job-{uuid.uuid4().hex[:8]}"

    adapter = FixtureSourceAdapter()
    storage = LocalStorageBackend()

    job = SyncJob(
        id=job_id,
        identity=SyncJobIdentity(
            target_id=f"target:{resource}",
            resource=resource,
            revision=args.revision,
            idempotency_key=args.idempotency_key or job_id,
            action="sync",
        ),
        status="planned",
        attempts=0,
        metadata={
            "include": args.include,
            "exclude": args.exclude,
            "checksum": args.checksum,
        },
    )

    if args.dry_run:
        print(f"[dry-run] Would sync {resource} as job {job.id}")
        print(f"  revision: {args.revision or 'latest'}")
        print(f"  include:  {args.include or 'all'}")
        print(f"  exclude:  {args.exclude or 'none'}")
        return

    print(f"Syncing {resource} (job {job.id})...")
    worker = LocalMirrorWorker(adapter=adapter, storage=storage)
    result = worker.run(job)
    print(f"  Status:  {result.status}")
    if result.asset_id:
        print(f"  Asset:   {result.asset_id}")
    if result.version_id:
        print(f"  Version: {result.version_id}")
    if result.error:
        print(f"  Error:   {result.error}")
    if result.files:
        print(f"  Files:   {len(result.files)}")


def _run_expire_command(args: Any) -> None:
    """Execute the ``expire`` sub-command."""
    if args.dry_run:
        print("[dry-run] Approval expiry worker — no pending requests (local mode)")
        print("  This worker processes pending/approved requests and expires")
        print("  those past their SLA target or approval validity period.")
        print("  In production, connect to a real approval store.")
        return

    # Local mode: run with an empty request list (demonstrates the worker interface)
    result = run_approval_expiry_worker([])
    print(f"Approval expiry worker complete:")
    print(f"  Expired:   {result.expired_count}")
    print(f"  Escalated: {result.escalated_count}")
    print(f"  Reminded:  {result.reminded_count}")
    print(f"  Errors:    {result.error_count}")
