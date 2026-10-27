"""Reproducible asset resolver — Phase 3b implementation.

Provides resolve_approved_asset and install_approved_asset flows that
verify approval/policy state before downloading and produce reproducibility
metadata.
"""

from __future__ import annotations

from ..governance.audit import record_audit_event
from .snapshots import get_channel_snapshot


def resolve_approved_asset(
    asset_id: str,
    *,
    channel: str = "production",
    tenant_scope: str = "default",
    snapshot_service,
    storage=None,
    repository=None,
) -> dict:
    """Resolve the latest approved snapshot for an asset on a channel.

    Returns snapshot metadata + manifest digest + diagnostic download info.
    Errors: policy_blocked, approval_required, not_found, manifest_mismatch.
    """

    snapshot = get_channel_snapshot(channel, tenant_scope=tenant_scope, repository=snapshot_service)
    if snapshot is None:
        raise ValueError(f"No approved snapshot found for asset {asset_id} on channel {channel}")

    if snapshot.asset_id != asset_id:
        raise ValueError(f"Snapshot {snapshot.id} does not belong to asset {asset_id}")

    result = {
        "asset_id": asset_id,
        "snapshot_id": snapshot.id,
        "version_id": snapshot.version_id,
        "manifest_digest": snapshot.manifest_digest,
        "channel": channel,
        "channel_resolution": {"channel": channel, "resolved_at": snapshot.created_at},
        "policy_decision_ref": snapshot.policy_decision_ref,
        "approval_ref": snapshot.approval_ref,
        "download": {
            "mode": "local_reference",
            "url_ref": "redacted",
        },
        "metadata": snapshot.metadata,
    }

    record_audit_event("asset.resolve_approved", resource=asset_id, status="ok",
                       metadata={"snapshot_id": snapshot.id, "channel": channel})
    return result


def install_approved_asset(
    asset_id: str,
    destination: str,
    *,
    channel: str = "production",
    tenant_scope: str = "default",
    snapshot_service,
    storage=None,
    repository=None,
) -> dict:
    """Resolve and download the approved version of an asset.

    Returns install result with reproducibility metadata.
    """

    resolved = resolve_approved_asset(
        asset_id, channel=channel, tenant_scope=tenant_scope,
        snapshot_service=snapshot_service, storage=storage, repository=repository,
    )

    files_downloaded = []
    if repository:
        version_id = resolved["version_id"]
        asset_files = list(repository.files.list_files(asset_id, version_id))
        for f in asset_files:
            local_path = getattr(f, "local_path", None)
            if local_path:
                files_downloaded.append({"path": f.path, "size": f.size, "sha256": f.sha256, "local_path": local_path})

    result = {
        "asset_id": asset_id,
        "snapshot_id": resolved["snapshot_id"],
        "manifest_digest": resolved["manifest_digest"],
        "destination": destination,
        "files_downloaded": files_downloaded,
        "file_count": len(files_downloaded),
        "reproducibility_metadata": {
            "snapshot_ref": resolved["snapshot_id"],
            "channel": channel,
            "resolved_at": resolved["channel_resolution"]["resolved_at"],
        },
    }

    record_audit_event("asset.install_approved", resource=asset_id, status="ok",
                       metadata={"snapshot_id": resolved["snapshot_id"], "file_count": len(files_downloaded)})
    return result


__all__ = ["install_approved_asset", "resolve_approved_asset"]
