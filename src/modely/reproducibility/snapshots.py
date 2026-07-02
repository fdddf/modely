"""Approved snapshot services.

Implements create, promote, rollback, list, and get operations on top of
the canonical domain model from domain/snapshots.py.
"""

from __future__ import annotations

import time
import uuid

from ..domain.snapshots import (
    ApprovedSnapshot,
    SnapshotChannel,
    SnapshotPromotion,
    SnapshotRollback,
    SnapshotRepository,
)
from ..governance.audit import record_audit_event


def _snap_id() -> str:
    return f"snap_{uuid.uuid4().hex[:12]}"


def _channel_id(tenant_scope: str, name: str) -> str:
    return f"ch_{tenant_scope.replace('/', '--')}:{name}"


def create_snapshot(
    *,
    asset_id: str,
    version_id: str,
    manifest_digest: str,
    tenant_scope: str = "default",
    channel_name: str = "dev",
    policy_decision_ref: str | None = None,
    approval_ref: str | None = None,
    created_by: str = "",
    repository: SnapshotRepository,
) -> ApprovedSnapshot:
    """Create an immutable approved snapshot."""

    snapshot = ApprovedSnapshot(
        id=_snap_id(),
        tenant_scope=tenant_scope,
        asset_id=asset_id,
        version_id=version_id,
        manifest_digest=manifest_digest,
        policy_decision_ref=policy_decision_ref,
        approval_ref=approval_ref,
        channel=channel_name,
        created_by=created_by,
        created_at=_now_iso(),
    )
    repository.save_snapshot(snapshot)

    # Ensure channel exists
    ch_id = _channel_id(tenant_scope, channel_name)
    existing = repository.get_channel(tenant_scope, channel_name)
    if existing is None:
        repository.save_channel(SnapshotChannel(
            id=ch_id, tenant_scope=tenant_scope, name=channel_name,
            current_snapshot_id=snapshot.id,
        ))

    record_audit_event("snapshot.create", resource=snapshot.id, status="ok", metadata={"asset_id": asset_id, "channel": channel_name})
    return snapshot


def promote_snapshot(
    snapshot_id: str,
    channel_name: str,
    *,
    promoted_by: str = "",
    reason: str = "",
    tenant_scope: str = "default",
    repository: SnapshotRepository,
) -> SnapshotPromotion:
    """Promote a snapshot to a channel, superseding the current snapshot."""

    snapshot = repository.get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot not found: {snapshot_id}")

    ch_id = _channel_id(tenant_scope, channel_name)
    channel = repository.get_channel(tenant_scope, channel_name)
    previous_snapshot_id = channel.current_snapshot_id if channel else None

    # Create promotion record
    promotion = SnapshotPromotion(
        id=f"promo_{uuid.uuid4().hex[:12]}",
        tenant_scope=tenant_scope,
        channel_id=ch_id,
        from_snapshot_id=previous_snapshot_id,
        to_snapshot_id=snapshot_id,
        reason=reason,
        promoted_by=promoted_by,
        promoted_at=_now_iso(),
    )
    repository.save_promotion(promotion)

    # Update the channel pointer
    if channel:
        channel.current_snapshot_id = snapshot_id
        channel.updated_by = promoted_by
        channel.updated_at = _now_iso()
        repository.save_channel(channel)
    else:
        repository.save_channel(SnapshotChannel(
            id=ch_id, tenant_scope=tenant_scope, name=channel_name,
            current_snapshot_id=snapshot_id, updated_by=promoted_by, updated_at=_now_iso(),
        ))

    record_audit_event("snapshot.promote", resource=snapshot_id, status="ok",
                       metadata={"channel": channel_name, "promoted_by": promoted_by, "previous": previous_snapshot_id})
    return promotion


def rollback_snapshot(
    snapshot_id: str,
    channel_name: str,
    *,
    reason: str = "",
    rolled_back_by: str = "",
    tenant_scope: str = "default",
    repository: SnapshotRepository,
) -> SnapshotRollback:
    """Rollback a channel to a prior snapshot."""

    ch_id = _channel_id(tenant_scope, channel_name)
    channel = repository.get_channel(tenant_scope, channel_name)
    if channel is None:
        raise ValueError(f"Channel not found: {channel_name}")

    # Find the promotion that set current_snapshot_id -> from_snapshot_id
    promotions = repository.get_promotion_history(ch_id)
    target_promotion = None
    for promo in promotions:
        if promo.to_snapshot_id == channel.current_snapshot_id:
            target_promotion = promo
            break

    if target_promotion is None or target_promotion.from_snapshot_id is None:
        raise ValueError(f"No prior snapshot to rollback to on channel {channel_name}")

    rollback = SnapshotRollback(
        id=f"rollback_{uuid.uuid4().hex[:12]}",
        tenant_scope=tenant_scope,
        channel_id=ch_id,
        from_snapshot_id=channel.current_snapshot_id,
        to_snapshot_id=target_promotion.from_snapshot_id,
        reason=reason,
        rolled_back_by=rolled_back_by,
        rolled_back_at=_now_iso(),
    )
    repository.save_rollback(rollback)

    # Revert channel to previous snapshot
    channel.current_snapshot_id = target_promotion.from_snapshot_id
    channel.updated_by = rolled_back_by
    channel.updated_at = _now_iso()
    repository.save_channel(channel)

    record_audit_event("snapshot.rollback", resource=snapshot_id, status="ok",
                       metadata={"channel": channel_name, "rolled_back_by": rolled_back_by, "reason": reason})

    # Mark the rolled-back snapshot
    current = repository.get_snapshot(snapshot_id)
    if current and hasattr(current, '__dict__'):
        # Snapshot is frozen, we record the rollback target in metadata only
        pass

    return rollback


def get_snapshot(snapshot_id: str, *, repository: SnapshotRepository) -> ApprovedSnapshot | None:
    return repository.get_snapshot(snapshot_id)


def list_snapshots(asset_id: str = "", *, repository: SnapshotRepository) -> list[ApprovedSnapshot]:
    return repository.list_snapshots(asset_id)


def get_channel_snapshot(channel_name: str, *, tenant_scope: str = "default", repository: SnapshotRepository) -> ApprovedSnapshot | None:
    channel = repository.get_channel(tenant_scope, channel_name)
    if channel is None or channel.current_snapshot_id is None:
        return None
    return repository.get_snapshot(channel.current_snapshot_id)


def get_snapshot_history(asset_id: str, *, repository: SnapshotRepository) -> list[dict]:
    """Return promotion/rollback timeline for an asset's snapshots."""
    snapshots = repository.list_snapshots(asset_id)
    history = []
    for snap in snapshots:
        ch_id = _channel_id(snap.tenant_scope, snap.channel)
        promotions = repository.get_promotion_history(ch_id)
        rollbacks = repository.get_rollback_history(ch_id)
        history.append({
            "snapshot_id": snap.id,
            "asset_id": snap.asset_id,
            "channel": snap.channel,
            "created_at": snap.created_at,
            "promotions": [p.to_dict() for p in promotions if p.to_snapshot_id == snap.id],
            "rollbacks": [r.to_dict() for r in rollbacks if r.from_snapshot_id == snap.id],
        })
    return history


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "create_snapshot",
    "get_channel_snapshot",
    "get_snapshot",
    "get_snapshot_history",
    "list_snapshots",
    "promote_snapshot",
    "rollback_snapshot",
]
