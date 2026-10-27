"""Sync job domain objects and states."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..types import ResourceSyncRun, ResourceSyncState, ResourceSyncTarget, SyncCenterReport

SYNC_JOB_STATES: tuple[str, ...] = (
    "registered",
    "planned",
    "syncing",
    "synced",
    "failed",
    "disabled",
    "enabled",
    "unsupported",
    "unchanged",
    "drifted",
)
SYNC_RUN_ACTIONS: tuple[str, ...] = ("add", "plan", "sync", "check", "catalog", "remove", "enable", "disable")


@dataclass
class SyncJobIdentity:
    """Stable identity for idempotent sync jobs."""

    target_id: str
    action: str
    resource: str | None = None
    revision: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_sync_job_state(value: str) -> bool:
    return value in SYNC_JOB_STATES


def is_sync_run_action(value: str) -> bool:
    return value in SYNC_RUN_ACTIONS


__all__ = [
    "SYNC_JOB_STATES",
    "SYNC_RUN_ACTIONS",
    "ResourceSyncRun",
    "ResourceSyncState",
    "ResourceSyncTarget",
    "SyncCenterReport",
    "SyncJobIdentity",
    "is_sync_job_state",
    "is_sync_run_action",
]
