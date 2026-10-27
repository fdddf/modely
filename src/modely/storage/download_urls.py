"""Internal and signed download URL helpers."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from ..governance.audit import record_audit_event


@dataclass
class DownloadURL:
    """Internal download URL metadata returned by storage/catalog APIs."""

    url: str
    expires_at: str | None = None
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def local_download_url(path: str) -> DownloadURL:
    """Return a local file URL for single-node/local storage backends."""

    return DownloadURL(url=f"file://{path}", metadata={"backend": "local"})


def authorize_download(principal, asset_id: str) -> bool:
    """Check whether a principal is authorized to download an asset.

    Delegates to RBAC permission evaluation using the ``asset:download`` action.
    """
    from ..governance.rbac import check_permission

    decision = check_permission(principal, "asset:download")
    return decision.allowed


def authorize_download_full(principal, asset, *, shared_secret: str = "") -> tuple[bool, str, dict]:
    """Full download authorization: permission check, visibility check, policy check, and audit emission.

    Returns a tuple of (authorized: bool, reason: str, audit_metadata: dict).

    The authorization pipeline:
    1. RBAC check: principal must have ``asset:download`` permission.
    2. Visibility check: principal must be able to discover the asset.
    3. Governance policy check: evaluate scan evidence and approval state against
       the active policy profile.  ``block`` decisions deny the download;
       ``require_approval`` decisions deny the download when no valid approval exists.
    4. Audit: the authorization decision is recorded (allow or deny).

    When *shared_secret* is provided and the download is authorized, the audit
    metadata includes a ``signature_base`` value that can be used to generate a
    signed download URL via ``generate_signed_url``.
    """
    from ..cataloging.visibility import check_visibility
    from ..governance.rbac import check_permission

    asset_id_str = getattr(asset, "id", str(asset))

    # 1. RBAC check
    if principal is None:
        audit_md = _emit_download_audit("asset:download", asset_id_str, "denied", "unauthenticated")
        return False, "unauthenticated", audit_md

    decision = check_permission(principal, "asset:download")
    if not decision.allowed:
        reason = f"missing permission: asset:download"
        audit_md = _emit_download_audit("asset:download", asset_id_str, "denied", reason, principal_id=principal.id)
        return False, reason, audit_md

    # 2. Visibility check
    if not check_visibility(principal, asset):
        reason = "visibility restriction prevents discovery"
        audit_md = _emit_download_audit("asset:download", asset_id_str, "denied", reason, principal_id=principal.id)
        return False, reason, audit_md

    # 3. Governance policy check
    from ..governance.policy_engine import evaluate_governance_policy

    # Build asset dict for policy evaluation
    asset_dict = _asset_to_policy_dict(asset)
    # Build principal dict for policy evaluation
    principal_dict = _principal_to_policy_dict(principal)
    # Extract scan evidence from asset metadata if available
    scan_evidence = asset_dict.get("scan_evidence", {}) or {}
    # Extract approval state from asset metadata if available
    approval_state = asset_dict.get("approval_state", {}) or {}

    policy_decision = evaluate_governance_policy(
        principal=principal_dict,
        asset=asset_dict,
        action="asset:download",
        scan_evidence=scan_evidence,
        approval_state=approval_state,
    )

    if policy_decision.blocked:
        reason = f"policy blocked: {'; '.join(policy_decision.reasons)}"
        audit_md = _emit_download_audit(
            "asset:download", asset_id_str, "denied", reason,
            principal_id=principal.id,
        )
        audit_md["policy_outcome"] = "block"
        audit_md["policy_rule_ids"] = policy_decision.matched_rule_ids
        return False, "policy_blocked", audit_md

    if policy_decision.outcome == "require_approval":
        # Check if a valid (non-expired) approval exists
        if not _has_valid_approval(approval_state):
            reason = f"approval required: {'; '.join(policy_decision.reasons)}"
            audit_md = _emit_download_audit(
                "asset:download", asset_id_str, "denied", reason,
                principal_id=principal.id,
            )
            audit_md["policy_outcome"] = "require_approval"
            audit_md["policy_rule_ids"] = policy_decision.matched_rule_ids
            return False, "approval_required", audit_md

    # 4. Authorized — emit audit and return
    reason = "authorized"
    if policy_decision.outcome == "warn":
        reason = f"authorized_with_warning: {'; '.join(policy_decision.reasons)}"
    audit_md = _emit_download_audit("asset:download", asset_id_str, "ok", reason, principal_id=principal.id)
    audit_md["policy_outcome"] = policy_decision.outcome
    if policy_decision.matched_rule_ids:
        audit_md["policy_rule_ids"] = policy_decision.matched_rule_ids
    if policy_decision.reasons:
        audit_md["policy_reasons"] = policy_decision.reasons

    # Include signature base for downstream signed URL generation
    if shared_secret:
        timestamp = str(int(time.time()))
        audit_md["signature_base"] = f"{asset_id_str}:{principal.id}:{timestamp}"
        audit_md["signature_timestamp"] = timestamp

    return True, "authorized", audit_md


def generate_signed_url(
    asset_id: str,
    principal_id: str,
    storage_path: str,
    *,
    shared_secret: str,
    ttl_seconds: int = 300,
    base_url: str = "",
) -> DownloadURL:
    """Generate a signed download URL with a short TTL.

    The signature is an HMAC-SHA256 over
    ``asset_id:principal_id:timestamp`` using *shared_secret*.

    *ttl_seconds* controls how long the link is valid (default 300s = 5 min).
    *base_url* is the server download endpoint prefix.

    Returns a ``DownloadURL`` with the signed URL, expiry, and metadata.
    """
    timestamp = int(time.time())
    expires_at_ts = timestamp + ttl_seconds

    signature_base = f"{asset_id}:{principal_id}:{timestamp}"
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        signature_base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    from datetime import datetime, timezone

    expires_at = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()

    url = (
        f"{base_url}/api/v1/assets/{asset_id}/download"
        f"?signature={signature}"
        f"&principal_id={principal_id}"
        f"&ts={timestamp}"
    )

    return DownloadURL(
        url=url,
        expires_at=expires_at,
        method="GET",
        metadata={
            "backend": "signed",
            "ttl_seconds": ttl_seconds,
            "principal_id": principal_id,
        },
    )


def verify_signed_url(
    asset_id: str,
    principal_id: str,
    timestamp: str,
    signature: str,
    *,
    shared_secret: str,
    max_age_seconds: int = 300,
) -> bool:
    """Verify a signed download URL signature and TTL.

    Returns ``True`` if the signature is valid and has not expired.
    """
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    # TTL expiry check
    now = int(time.time())
    if now - ts > max_age_seconds:
        return False

    # HMAC verification
    expected_signature = hmac.new(
        shared_secret.encode("utf-8"),
        f"{asset_id}:{principal_id}:{timestamp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


def _emit_download_audit(
    action: str,
    asset_id: str,
    status: str,
    reason: str = "",
    *,
    principal_id: str = "",
) -> dict:
    """Emit a download audit event and return the event metadata."""
    metadata: dict[str, Any] = {"reason": reason, "authorization_phase": "2b"}
    if principal_id:
        metadata["principal_id"] = principal_id
    return record_audit_event(
        action=action,
        resource=asset_id,
        status=status,
        metadata=metadata,
    )


def _has_valid_approval(approval_state: dict) -> bool:
    """Check if a valid (approved, non-expired) approval exists.

    An approval is valid if its status is ``approved`` and it has not expired.
    Expiry is checked against ``expires_at`` if present, otherwise the
    approval is presumed still valid.
    """
    if not isinstance(approval_state, dict):
        return False
    status = approval_state.get("status", "none")
    if status != "approved":
        return False
    expires_at = approval_state.get("expires_at")
    if expires_at is not None:
        from datetime import datetime, timezone
        try:
            expiry = datetime.fromisoformat(str(expires_at))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now >= expiry:
                return False
        except (ValueError, TypeError):
            # Unparseable expiry — treat as invalid for safety
            return False
    return True


def _asset_to_policy_dict(asset) -> dict[str, Any]:
    """Convert an asset object (dataclass, dict, or plain object) into a dict
    suitable for ``evaluate_governance_policy``.

    Covers Asset dataclass instances, dicts, and generic objects with attributes.
    Also reads license and tags from nested ``metadata`` when not at top level.
    """
    if hasattr(asset, "to_dict") and not isinstance(asset, dict):
        result = dict(asset.to_dict())
    elif isinstance(asset, dict):
        result = dict(asset)
    else:
        result = {}
        for attr in ("id", "repo_id", "repo_type", "source", "license",
                      "tags", "files", "size", "file_count", "checksum",
                      "operational_state", "visibility", "tenant_scope",
                      "metadata", "scan", "scan_evidence", "approval_state"):
            if hasattr(asset, attr):
                result[attr] = getattr(asset, attr)

    # Enrich from metadata sidecar (license, tags are stored there by catalog_from_cache)
    meta = result.get("metadata")
    if isinstance(meta, dict):
        if not result.get("license"):
            result["license"] = meta.get("license")
        if not result.get("tags"):
            result["tags"] = meta.get("tags") or []
        if not result.get("files"):
            result["files"] = meta.get("files") or []
    return result


def _principal_to_policy_dict(principal) -> dict[str, Any]:
    """Convert a principal object into a dict suitable for ``evaluate_governance_policy``."""
    if hasattr(principal, "to_dict") and not isinstance(principal, dict):
        return principal.to_dict()
    if isinstance(principal, dict):
        return dict(principal)
    result: dict[str, Any] = {}
    for attr in ("id", "username", "department", "service_account",
                  "display_name", "email", "tenant_scope", "roles"):
        if hasattr(principal, attr):
            result[attr] = getattr(principal, attr)
    return result


__all__ = [
    "DownloadURL",
    "_asset_to_policy_dict",
    "_has_valid_approval",
    "_principal_to_policy_dict",
    "authorize_download",
    "authorize_download_full",
    "generate_signed_url",
    "local_download_url",
    "verify_signed_url",
]
