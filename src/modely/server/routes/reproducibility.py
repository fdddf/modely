"""Reproducibility route adapters for Phase 3 enterprise API.

Routes accept injected services and return envelope-wrapped payloads.
"""

from __future__ import annotations

from ..schemas.envelopes import error_response, generate_request_id, success_response
from ..schemas.reproducibility import (
    CIGateRequest,
    CIGateResourceResult,
    CIGateResponse,
    LockfileResourceResult,
    LockfileValidateRequest,
    LockfileValidateResponse,
    ManifestDiffRequest,
    ManifestDiffResponse,
    ResolveApprovedRequest,
    ResolveApprovedResponse,
)


def validate_lockfile(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Validate an enterprise lockfile through an injected lockfile service.

    POST /api/v1/lockfiles/validate

    Accepts ``lockfile_path`` or ``lockfile_content``.  Delegates to the
    service for schema v3/v4 reading and enterprise validation.
    """

    req = LockfileValidateRequest(
        lockfile_path=payload.get("lockfile_path"),
        lockfile_content=payload.get("lockfile_content"),
        profile=payload.get("profile", "production"),
        fail_on_warnings=payload.get("fail_on_warnings", False),
    )

    if not req.lockfile_path and not req.lockfile_content:
        return error_response(
            "validation_error",
            "Either lockfile_path or lockfile_content is required.",
            request_id=request_id,
        )

    try:
        # Delegate to the lockfile validation service
        result = service.validate_enterprise_lock(
            path=req.lockfile_path,
            content=req.lockfile_content,
            profile=req.profile,
            fail_on_warnings=req.fail_on_warnings,
        )
    except FileNotFoundError:
        return error_response(
            "not_found",
            f"Lockfile not found: {req.lockfile_path}",
            request_id=request_id,
        )
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    resources = [
        LockfileResourceResult(
            uri=r.get("uri", ""),
            status=r.get("status", "passed"),
            checksum_ok=r.get("checksum_ok", True),
            approval_ok=r.get("approval_ok", True),
            policy_ok=r.get("policy_ok", True),
            snapshot_ref_valid=r.get("snapshot_ref_valid", True),
            errors=r.get("errors", []),
            warnings=r.get("warnings", []),
        )
        for r in result.get("resources", [])
    ]

    summary = {
        "total": len(resources),
        "passed": sum(1 for r in resources if r.status == "passed"),
        "failed": sum(1 for r in resources if r.status == "failed"),
        "warning": sum(1 for r in resources if r.status == "warning"),
    }

    response = LockfileValidateResponse(
        lockfile_path=req.lockfile_path,
        schema_version=result.get("schema_version", 4),
        status="passed" if not any(r.status == "failed" for r in resources) else "failed",
        resources=resources,
        summary=summary,
    )
    return success_response(response.to_dict(), request_id=request_id)


def diff_manifests_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Diff two manifests or asset versions.

    POST /api/v1/manifests/diff

    Accepts ``left_version_id`` + ``right_version_id`` (query repository)
    or ``left_manifest`` + ``right_manifest`` (inline content).
    """

    left_vid = payload.get("left_version_id")
    right_vid = payload.get("right_version_id")
    left_manifest = payload.get("left_manifest")
    right_manifest = payload.get("right_manifest")

    if not ((left_vid and right_vid) or (left_manifest and right_manifest)):
        return error_response(
            "validation_error",
            "Provide either (left_version_id, right_version_id) or (left_manifest, right_manifest).",
            request_id=request_id,
        )

    try:
        if left_vid and right_vid:
            result = service.diff_asset_versions(left_vid, right_vid)
        else:
            result = service.diff_manifest_dicts(left_manifest, right_manifest)
    except (KeyError, FileNotFoundError) as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    response = ManifestDiffResponse(
        added_files=result.get("added", []),
        removed_files=result.get("removed", []),
        changed_files=result.get("changed", []),
        metadata_delta=result.get("metadata_delta", {}),
        license_delta=result.get("license_delta", {}),
        risk_delta=result.get("risk_delta", {}),
        policy_delta=result.get("policy_delta", {}),
        model_card_delta=result.get("model_card_delta", {}),
        summary=result.get("summary", {}),
    )
    return success_response(response.to_dict(), request_id=request_id)


# -- Snapshot endpoints (3a-3) -------------------------------------------------


def create_snapshot_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Create an approved snapshot.

    POST /api/v1/snapshots
    """

    asset_id = payload.get("asset_id", "").strip()
    version_id = payload.get("version_id", "").strip()
    manifest_digest = payload.get("manifest_digest", "").strip()

    if not asset_id or not version_id or not manifest_digest:
        return error_response("validation_error", "asset_id, version_id, and manifest_digest are required.", request_id=request_id)

    try:
        snapshot = service.create_snapshot(
            asset_id=asset_id,
            version_id=version_id,
            manifest_digest=manifest_digest,
            tenant_scope=payload.get("tenant_scope", "default"),
            channel_name=payload.get("channel_name", "dev"),
            policy_decision_ref=payload.get("policy_decision_ref"),
            approval_ref=payload.get("approval_ref"),
            created_by=payload.get("created_by", ""),
        )
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    return success_response(snapshot.to_dict(), request_id=request_id)


def list_snapshots_route(service, *, request_id: str = "req_unknown", **query_params) -> dict:
    """List snapshots, optionally filtered by asset_id.

    GET /api/v1/snapshots?asset_id=
    """

    asset_id = query_params.get("asset_id", "").strip() or None
    snapshots = service.list_snapshots(asset_id=asset_id)
    return success_response(
        {"snapshots": [s.to_dict() for s in snapshots], "count": len(snapshots)},
        request_id=request_id,
    )


def get_snapshot_route(service, snapshot_id: str, *, request_id: str = "req_unknown") -> dict:
    """Get a single snapshot by id.

    GET /api/v1/snapshots/{id}
    """

    snapshot = service.get_snapshot(snapshot_id)
    if snapshot is None:
        return error_response("not_found", f"Snapshot not found: {snapshot_id}", request_id=request_id)
    return success_response(snapshot.to_dict(), request_id=request_id)


def promote_snapshot_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Promote a snapshot to a channel.

    POST /api/v1/snapshots/promote
    """

    snapshot_id = payload.get("snapshot_id", "").strip()
    channel_name = payload.get("channel_name", "").strip()

    if not snapshot_id or not channel_name:
        return error_response("validation_error", "snapshot_id and channel_name are required.", request_id=request_id)

    try:
        result = service.promote_snapshot(
            snapshot_id=snapshot_id,
            channel_name=channel_name,
            promoted_by=payload.get("promoted_by", ""),
            reason=payload.get("reason", ""),
            tenant_scope=payload.get("tenant_scope", "default"),
        )
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    return success_response(result.to_dict(), request_id=request_id)


def rollback_snapshot_route(service, snapshot_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    """Rollback a channel to a prior snapshot.

    POST /api/v1/snapshots/{id}/rollback
    """

    channel_name = payload.get("channel_name", "").strip()
    if not channel_name:
        # default to the snapshot's own channel
        snap = service.get_snapshot(snapshot_id)
        if snap is None:
            return error_response("not_found", f"Snapshot not found: {snapshot_id}", request_id=request_id)
        channel_name = snap.channel

    try:
        result = service.rollback_snapshot(
            snapshot_id=snapshot_id,
            channel_name=channel_name,
            reason=payload.get("reason", ""),
            rolled_back_by=payload.get("rolled_back_by", ""),
            tenant_scope=payload.get("tenant_scope", "default"),
        )
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    return success_response(result.to_dict(), request_id=request_id)


def snapshot_history_route(service, snapshot_id: str, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Get promotion/rollback history for a snapshot.

    GET /api/v1/snapshots/{id}/history
    """

    history = service.get_snapshot_history(snapshot_id)
    return success_response({"snapshot_id": snapshot_id, "history": history}, request_id=request_id)


# -- CI Gate endpoint (3b-1) ---------------------------------------------------


def evaluate_ci_gate_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Evaluate a CI gate over a lockfile.

    POST /api/v1/ci-gates/evaluate
    """

    lockfile_path = payload.get("lockfile_path", "").strip()
    if not lockfile_path:
        return error_response("validation_error", "lockfile_path is required.", request_id=request_id)

    profile = payload.get("profile", "production")
    fail_on_warnings = payload.get("fail_on_warnings", False)
    policy_path = payload.get("policy_path")

    try:
        result = service.evaluate_ci_gate(
            lockfile_path=lockfile_path,
            profile=profile,
            fail_on_warnings=fail_on_warnings,
            policy_path=policy_path,
        )
    except FileNotFoundError:
        return error_response("not_found", f"Lockfile not found: {lockfile_path}", request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    resources = [
        CIGateResourceResult(
            uri=r.get("uri", ""), status=r.get("status", "passed"),
            errors=r.get("errors", []), warnings=r.get("warnings", []),
            checksum_ok=r.get("checksum_ok", True), policy_ok=r.get("policy_ok", True), approval_ok=r.get("approval_ok", True),
        )
        for r in result.get("resources", [])
    ]

    response = CIGateResponse(
        status=result.get("status", "passed"),
        exit_code=result.get("exit_code", 0),
        profile=profile,
        lockfile_path=lockfile_path,
        resources=resources,
        summary=result.get("summary", {}),
    )
    return success_response(response.to_dict(), request_id=request_id)


# -- Platform handoff endpoints (3c-2) ----------------------------------------


def resolve_approved_route(service, asset_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    """Resolve an approved asset for platform consumption.

    POST /api/v1/assets/{id}/resolve-approved
    """

    channel = payload.get("requested_channel", "production")
    try:
        result = service.resolve_approved_asset(
            asset_id=asset_id,
            channel=channel,
            tenant_scope=payload.get("tenant_scope", "default"),
        )
    except ValueError as exc:
        msg = str(exc)
        if "No approved snapshot" in msg:
            return error_response("approval_required", msg, request_id=request_id)
        return error_response("not_found", msg, request_id=request_id)

    response = ResolveApprovedResponse(
        asset_id=asset_id,
        snapshot_id=result.get("snapshot_id", ""),
        version_id=result.get("version_id", ""),
        manifest_digest=result.get("manifest_digest", ""),
        channel_resolution=result.get("channel_resolution", {}),
        download=result.get("download", {"mode": "local_reference", "url_ref": "redacted"}),
        policy_decision_ref=result.get("policy_decision_ref"),
        approval_ref=result.get("approval_ref"),
        audit_ref=result.get("audit_ref"),
    )
    return success_response(response.to_dict(), request_id=request_id)


def record_usage_event_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Record a platform usage event.

    POST /api/v1/platform-usage-events
    """

    platform = payload.get("platform", "").strip()
    asset_id = payload.get("asset_id", "").strip()
    if not platform or not asset_id:
        return error_response("validation_error", "platform and asset_id are required.", request_id=request_id)

    event = service.record_usage_event(
        platform=platform,
        job_id=payload.get("job_id", ""),
        asset_id=asset_id,
        snapshot_id=payload.get("snapshot_id", ""),
        manifest_digest=payload.get("manifest_digest", ""),
        action=payload.get("action", "deploy"),
        result=payload.get("result", "success"),
        metadata=payload.get("metadata", {}),
    )
    return success_response(event, request_id=request_id)


__all__ = [
    "create_snapshot_route",
    "diff_manifests_route",
    "evaluate_ci_gate_route",
    "get_snapshot_route",
    "list_snapshots_route",
    "promote_snapshot_route",
    "record_usage_event_route",
    "resolve_approved_route",
    "rollback_snapshot_route",
    "snapshot_history_route",
    "validate_lockfile",
]
