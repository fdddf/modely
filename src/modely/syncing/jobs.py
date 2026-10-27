"""Sync job creation and lookup helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..domain.sync_jobs import SYNC_JOB_STATES, SyncJobIdentity, is_sync_job_state


@dataclass
class SyncJob:
    """Minimal job contract shared by future server routes and workers."""

    id: str
    identity: SyncJobIdentity
    status: str = "registered"
    attempts: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_sync_job_state(self.status):
            raise ValueError(f"Unsupported sync job status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_sync_job(job_id: str, *, target_id: str, action: str = "sync", resource: str | None = None, revision: str | None = None) -> SyncJob:
    """Create a minimal sync job DTO without executing work inline."""

    return SyncJob(job_id, SyncJobIdentity(target_id=target_id, action=action, resource=resource, revision=revision))


__all__ = ["SYNC_JOB_STATES", "SyncJob", "create_sync_job"]
