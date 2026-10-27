"""Sync API schemas for the Phase 1b enterprise API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SyncJobResponse:
    """Stable response shape for sync job create and status APIs."""

    id: str
    target_id: str
    status: str
    resource: str = ""
    action: str = "sync"
    attempts: int = 0
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SyncJobLogResponse:
    """Response shape for sync job log diagnostics."""

    job_id: str
    status: str
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["SyncJobLogResponse", "SyncJobResponse"]
