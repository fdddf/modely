"""Approved snapshot domain objects.

Canonical model from docs/specs/enterprise-domain-model.md:
  - ApprovedSnapshot: immutable snapshot of asset version + manifest + policy/approval evidence
  - SnapshotChannel: mutable channel pointer (dev, staging, production)
  - SnapshotPromotion: audited promotion record
  - SnapshotRollback: audited rollback record
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


# -- Repository protocol -------------------------------------------------------


class SnapshotRepository(Protocol):
    """Backend-neutral repository contract for snapshot persistence."""

    def save_snapshot(self, snapshot: "ApprovedSnapshot") -> "ApprovedSnapshot": ...
    def get_snapshot(self, snapshot_id: str) -> "ApprovedSnapshot | None": ...
    def list_snapshots(self, asset_id: str = "") -> list["ApprovedSnapshot"]: ...
    def get_channel(self, tenant_scope: str, channel_name: str) -> "SnapshotChannel | None": ...
    def save_channel(self, channel: "SnapshotChannel") -> "SnapshotChannel": ...
    def save_promotion(self, promotion: "SnapshotPromotion") -> "SnapshotPromotion": ...
    def save_rollback(self, rollback: "SnapshotRollback") -> "SnapshotRollback": ...
    def get_promotion_history(self, channel_id: str) -> list["SnapshotPromotion"]: ...
    def get_rollback_history(self, channel_id: str) -> list["SnapshotRollback"]: ...


# -- Domain entities -----------------------------------------------------------


@dataclass(frozen=True)
class ApprovedSnapshot:
    """Immutable approved snapshot of an asset version.

    Once created, fields cannot be changed. Promotion/rollback creates
    new audit records rather than mutating this object.
    """

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
class SnapshotChannel:
    """Mutable channel pointer. Updated on promotion/rollback."""

    id: str
    tenant_scope: str
    name: str
    project_id: str | None = None
    environment_id: str | None = None
    current_snapshot_id: str | None = None
    updated_by: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotPromotion:
    """Audit record for a snapshot promotion."""

    id: str
    tenant_scope: str
    channel_id: str
    from_snapshot_id: str | None = None
    to_snapshot_id: str = ""
    reason: str = ""
    promoted_by: str = ""
    promoted_at: str = ""
    audit_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotRollback:
    """Audit record for a snapshot rollback."""

    id: str
    tenant_scope: str
    channel_id: str
    from_snapshot_id: str | None = None
    to_snapshot_id: str = ""
    reason: str = ""
    rolled_back_by: str = ""
    rolled_back_at: str = ""
    audit_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "ApprovedSnapshot",
    "SnapshotChannel",
    "SnapshotPromotion",
    "SnapshotRepository",
    "SnapshotRollback",
]
