"""Reproducibility schemas for Phase 3 enterprise API.

Created in Phase 3a Task 1, extended by 3a Task 2, 3a Task 3, 3b, and 3c.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# -- Lockfile validation schemas (3a-1) ----------------------------------------

@dataclass
class LockfileValidateRequest:
    """Request to validate an enterprise lockfile."""

    lockfile_path: str | None = None
    lockfile_content: dict[str, Any] | None = None
    profile: str = "production"
    fail_on_warnings: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LockfileResourceResult:
    """Per-resource validation result within a lockfile."""

    uri: str
    status: str  # "passed", "failed", "warning"
    checksum_ok: bool = True
    approval_ok: bool = True
    policy_ok: bool = True
    snapshot_ref_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LockfileValidateResponse:
    """Response from lockfile validation."""

    lockfile_path: str | None = None
    schema_version: int = 4
    status: str = "passed"
    resources: list[LockfileResourceResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["resources"] = [r.to_dict() for r in self.resources]
        return payload


# -- Manifest diff schemas (3a-2) ---------------------------------------------

@dataclass
class ManifestDiffRequest:
    """Request to diff two manifests or asset versions."""

    left_version_id: str | None = None
    right_version_id: str | None = None
    left_manifest: dict[str, Any] | None = None
    right_manifest: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ManifestDiffResponse:
    """Response from manifest/version comparison."""

    added_files: list[dict[str, Any]] = field(default_factory=list)
    removed_files: list[dict[str, Any]] = field(default_factory=list)
    changed_files: list[dict[str, Any]] = field(default_factory=list)
    metadata_delta: dict[str, Any] = field(default_factory=dict)
    license_delta: dict[str, Any] = field(default_factory=dict)
    risk_delta: dict[str, Any] = field(default_factory=dict)
    policy_delta: dict[str, Any] = field(default_factory=dict)
    model_card_delta: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Snapshot schemas (3a-3) ---------------------------------------------------

@dataclass
class SnapshotResponse:
    """Response shape for approved snapshot APIs."""

    id: str
    tenant_scope: str
    asset_id: str
    version_id: str
    manifest_digest: str
    policy_decision_ref: str | None = None
    approval_ref: str | None = None
    channel: str = "dev"
    created_by: str = ""
    created_at: str = ""
    supersedes: str | None = None
    rollback_target: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotCreateRequest:
    """Request to create an approved snapshot."""

    asset_id: str = ""
    version_id: str = ""
    manifest_digest: str = ""
    tenant_scope: str = "default"
    channel_name: str = "dev"
    policy_decision_ref: str | None = None
    approval_ref: str | None = None
    created_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotPromotionRequest:
    """Request to promote a snapshot to a channel."""

    snapshot_id: str = ""
    channel_name: str = ""
    promoted_by: str = ""
    reason: str = ""
    tenant_scope: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotPromotionResponse:
    """Response from a snapshot promotion."""

    id: str
    channel_id: str
    from_snapshot_id: str | None = None
    to_snapshot_id: str = ""
    promoted_by: str = ""
    promoted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotRollbackRequest:
    """Request to rollback a channel to a prior snapshot."""

    reason: str = ""
    rolled_back_by: str = ""
    tenant_scope: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotHistoryEntry:
    """One entry in a snapshot's promotion/rollback timeline."""

    snapshot_id: str
    asset_id: str
    channel: str
    created_at: str
    promotions: list[dict[str, Any]] = field(default_factory=list)
    rollbacks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- CI Gate schemas (3b-1) ----------------------------------------------------

@dataclass
class CIGateRequest:
    """Request to evaluate a CI gate over a lockfile."""

    lockfile_path: str = ""
    profile: str = "production"
    fail_on_warnings: bool = False
    policy_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CIGateResourceResult:
    """Per-resource result within a CI gate evaluation."""

    uri: str = ""
    status: str = "passed"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checksum_ok: bool = True
    policy_ok: bool = True
    approval_ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CIGateResponse:
    """Response from CI gate evaluation."""

    status: str = "passed"
    exit_code: int = 0
    profile: str = "production"
    lockfile_path: str = ""
    resources: list[CIGateResourceResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["resources"] = [r.to_dict() for r in self.resources]
        return payload


# -- Platform handoff schemas (3c-2) ------------------------------------------

@dataclass
class ResolveApprovedRequest:
    """Request to resolve an approved asset for platform consumption."""

    tenant_scope: dict[str, str] = field(default_factory=dict)
    requested_channel: str = "production"
    requested_snapshot_id: str | None = None
    requested_actions: list[str] = field(default_factory=list)
    platform: str = ""
    job_id: str = ""
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolveApprovedResponse:
    """Response from an approved asset resolution."""

    asset_id: str = ""
    snapshot_id: str = ""
    version_id: str = ""
    manifest_digest: str = ""
    channel_resolution: dict[str, str] = field(default_factory=dict)
    download: dict[str, str] = field(default_factory=dict)
    policy_decision_ref: str | None = None
    approval_ref: str | None = None
    audit_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlatformUsageEventRequest:
    """Request to record a platform usage event."""

    tenant_scope: dict[str, str] = field(default_factory=dict)
    platform: str = ""
    job_id: str = ""
    asset_id: str = ""
    snapshot_id: str = ""
    manifest_digest: str = ""
    action: str = ""
    result: str = "success"
    timestamp: str = ""
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "CIGateRequest",
    "CIGateResourceResult",
    "CIGateResponse",
    "LockfileResourceResult",
    "LockfileValidateRequest",
    "LockfileValidateResponse",
    "ManifestDiffRequest",
    "ManifestDiffResponse",
    "PlatformUsageEventRequest",
    "ResolveApprovedRequest",
    "ResolveApprovedResponse",
    "SnapshotCreateRequest",
    "SnapshotHistoryEntry",
    "SnapshotPromotionRequest",
    "SnapshotPromotionResponse",
    "SnapshotResponse",
    "SnapshotRollbackRequest",
]
