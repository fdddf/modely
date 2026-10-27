"""Audit event domain objects and canonical event type constants.

This module defines the complete set of audit event types for Phase 2 enterprise
operations and reserved Phase 3 token event types.  All audit producers and
consumers should reference these constants rather than ad-hoc strings.

Canonical event type structure is ``<category>.<event>``.  Event categories
correspond to governance domains: auth, asset, sync, policy, approval, admin,
access, report, and token (Phase 3 reserved).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Canonical event type constants — organized by audit category
# ---------------------------------------------------------------------------

# Auth events
AUDIT_AUTH_LOGIN = "user.login"
AUDIT_AUTH_LOGIN_FAILED = "user.login_failed"
AUDIT_AUTH_LOGOUT = "user.logout"

# Catalog events
AUDIT_CATALOG_ASSET_VIEW = "asset.view"
AUDIT_CATALOG_ASSET_SEARCH = "asset.search"

# Download events
AUDIT_DOWNLOAD = "asset.download"
AUDIT_DOWNLOAD_DENIED = "asset.download_denied"
AUDIT_DOWNLOAD_URL_ISSUED = "asset.download_url_issued"

# Sync events
AUDIT_SYNC_JOB_CREATED = "sync.job_created"
AUDIT_SYNC_JOB_STARTED = "sync.job_started"
AUDIT_SYNC_JOB_SUCCEEDED = "sync.job_succeeded"
AUDIT_SYNC_JOB_FAILED = "sync.job_failed"

# Policy events
AUDIT_POLICY_EVALUATED = "policy.evaluated"
AUDIT_POLICY_CHANGED = "policy.changed"
AUDIT_POLICY_PROFILE_CREATED = "policy.profile_created"
AUDIT_POLICY_PROFILE_UPDATED = "policy.profile_updated"
AUDIT_POLICY_PROFILE_ARCHIVED = "policy.profile_archived"

# Approval events
AUDIT_APPROVAL_REQUESTED = "approval.requested"
AUDIT_APPROVAL_APPROVED = "approval.approved"
AUDIT_APPROVAL_REJECTED = "approval.rejected"
AUDIT_APPROVAL_CANCELLED = "approval.cancelled"
AUDIT_APPROVAL_EXPIRED = "approval.expired"
AUDIT_APPROVAL_ESCALATED = "approval.escalated"

# Admin events
AUDIT_ADMIN_ROLE_ASSIGNED = "admin.role_assigned"
AUDIT_ADMIN_ROLE_REVOKED = "admin.role_revoked"
AUDIT_ADMIN_TEAM_CREATED = "admin.team_created"
AUDIT_ADMIN_ASSET_DELETED = "admin.asset_deleted"
AUDIT_ADMIN_QUOTA_CHANGED = "admin.quota_changed"

# Restricted / break-glass events
AUDIT_ACCESS_RESTRICTED_ATTEMPT = "access.restricted_attempt"
AUDIT_ACCESS_BREAK_GLASS_USED = "access.break_glass_used"

# Report events
AUDIT_REPORT_EXPORTED = "report.exported"

# Phase 3 reserved — token / service account events
AUDIT_TOKEN_ISSUED = "token.issued"
AUDIT_TOKEN_REVOKED = "token.revoked"
AUDIT_TOKEN_ROTATED = "token.rotated"

# Credential lifecycle events — source credential governance
AUDIT_CREDENTIAL_CREATED = "credential.created"
AUDIT_CREDENTIAL_FAILED = "credential.failed"
AUDIT_CREDENTIAL_REVOKED = "credential.revoked"
AUDIT_CREDENTIAL_ROTATED = "credential.rotated"
AUDIT_CREDENTIAL_USED = "credential.used"


# ---------------------------------------------------------------------------
# Convenience groupings
# ---------------------------------------------------------------------------

#: Complete canonical set used by ``is_audit_action`` validation.
AUDIT_ACTIONS: tuple[str, ...] = (
    # Auth
    AUDIT_AUTH_LOGIN,
    AUDIT_AUTH_LOGIN_FAILED,
    AUDIT_AUTH_LOGOUT,
    # Catalog
    AUDIT_CATALOG_ASSET_VIEW,
    AUDIT_CATALOG_ASSET_SEARCH,
    # Download
    AUDIT_DOWNLOAD,
    AUDIT_DOWNLOAD_DENIED,
    AUDIT_DOWNLOAD_URL_ISSUED,
    # Sync
    AUDIT_SYNC_JOB_CREATED,
    AUDIT_SYNC_JOB_STARTED,
    AUDIT_SYNC_JOB_SUCCEEDED,
    AUDIT_SYNC_JOB_FAILED,
    # Policy
    AUDIT_POLICY_EVALUATED,
    AUDIT_POLICY_CHANGED,
    AUDIT_POLICY_PROFILE_CREATED,
    AUDIT_POLICY_PROFILE_UPDATED,
    AUDIT_POLICY_PROFILE_ARCHIVED,
    # Approval
    AUDIT_APPROVAL_REQUESTED,
    AUDIT_APPROVAL_APPROVED,
    AUDIT_APPROVAL_REJECTED,
    AUDIT_APPROVAL_CANCELLED,
    AUDIT_APPROVAL_EXPIRED,
    AUDIT_APPROVAL_ESCALATED,
    # Admin
    AUDIT_ADMIN_ROLE_ASSIGNED,
    AUDIT_ADMIN_ROLE_REVOKED,
    AUDIT_ADMIN_TEAM_CREATED,
    AUDIT_ADMIN_ASSET_DELETED,
    AUDIT_ADMIN_QUOTA_CHANGED,
    # Restricted / break-glass
    AUDIT_ACCESS_RESTRICTED_ATTEMPT,
    AUDIT_ACCESS_BREAK_GLASS_USED,
    # Report
    AUDIT_REPORT_EXPORTED,
    # Phase 3 reserved
    AUDIT_TOKEN_ISSUED,
    AUDIT_TOKEN_REVOKED,
    AUDIT_TOKEN_ROTATED,
    # Credential lifecycle
    AUDIT_CREDENTIAL_CREATED,
    AUDIT_CREDENTIAL_FAILED,
    AUDIT_CREDENTIAL_REVOKED,
    AUDIT_CREDENTIAL_ROTATED,
    AUDIT_CREDENTIAL_USED,
)

#: Actions that directly affect access control or policy decisions.
AUDIT_ACTIONS_SECURITY_SENSITIVE: frozenset[str] = frozenset({
    AUDIT_AUTH_LOGIN_FAILED,
    AUDIT_ACCESS_RESTRICTED_ATTEMPT,
    AUDIT_ACCESS_BREAK_GLASS_USED,
    AUDIT_DOWNLOAD_DENIED,
    AUDIT_ADMIN_ROLE_ASSIGNED,
    AUDIT_ADMIN_ROLE_REVOKED,
    AUDIT_POLICY_CHANGED,
    AUDIT_APPROVAL_ESCALATED,
    AUDIT_TOKEN_ISSUED,
    AUDIT_TOKEN_REVOKED,
    AUDIT_TOKEN_ROTATED,
    AUDIT_CREDENTIAL_CREATED,
    AUDIT_CREDENTIAL_FAILED,
    AUDIT_CREDENTIAL_REVOKED,
    AUDIT_CREDENTIAL_ROTATED,
})


# ---------------------------------------------------------------------------
# Audit event DTO
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
    """Normalized audit event DTO shared by local and future server flows.

    Fields:
        action: Canonical event type e.g. ``asset.download``, ``approval.requested``.
        actor: Principal identifier that triggered the event.
        resource: The asset, policy profile, or other resource identifier.
        created_at: ISO-8601 UTC timestamp (defaults to now if left ``None`` by
            the recorder).
        outcome: ``"ok"`` or ``"denied"`` — short status for filtering.
        metadata: Arbitrary context that will be redacted before storage.
        tenant_scope: Optional tenant scoping for multi-tenant deployments.
    """

    action: str
    actor: str | None = None
    resource: str | None = None
    created_at: str | None = None
    outcome: str = "ok"
    metadata: dict[str, Any] = field(default_factory=dict)
    tenant_scope: dict[str, Any] | None = None

    def to_dict(self, *, redact: bool = False) -> dict[str, Any]:
        """Return the event as a dictionary.

        When *redact* is ``True``, sensitive metadata fields are redacted.
        """
        d = asdict(self)
        if redact and d.get("metadata"):
            from ..governance.redaction import redact_mapping

            d["metadata"] = redact_mapping(d["metadata"])
        return d


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def is_audit_action(value: str) -> bool:
    """Return ``True`` when *value* is a canonical audit action."""
    return value in AUDIT_ACTIONS


def is_security_sensitive_action(value: str) -> bool:
    """Return ``True`` when *value* is a security-sensitive audit action."""
    return value in AUDIT_ACTIONS_SECURITY_SENSITIVE


__all__ = [
    # Constants — auth
    "AUDIT_AUTH_LOGIN",
    "AUDIT_AUTH_LOGIN_FAILED",
    "AUDIT_AUTH_LOGOUT",
    # Constants — catalog
    "AUDIT_CATALOG_ASSET_VIEW",
    "AUDIT_CATALOG_ASSET_SEARCH",
    # Constants — download
    "AUDIT_DOWNLOAD",
    "AUDIT_DOWNLOAD_DENIED",
    "AUDIT_DOWNLOAD_URL_ISSUED",
    # Constants — sync
    "AUDIT_SYNC_JOB_CREATED",
    "AUDIT_SYNC_JOB_STARTED",
    "AUDIT_SYNC_JOB_SUCCEEDED",
    "AUDIT_SYNC_JOB_FAILED",
    # Constants — policy
    "AUDIT_POLICY_EVALUATED",
    "AUDIT_POLICY_CHANGED",
    "AUDIT_POLICY_PROFILE_CREATED",
    "AUDIT_POLICY_PROFILE_UPDATED",
    "AUDIT_POLICY_PROFILE_ARCHIVED",
    # Constants — approval
    "AUDIT_APPROVAL_REQUESTED",
    "AUDIT_APPROVAL_APPROVED",
    "AUDIT_APPROVAL_REJECTED",
    "AUDIT_APPROVAL_CANCELLED",
    "AUDIT_APPROVAL_EXPIRED",
    "AUDIT_APPROVAL_ESCALATED",
    # Constants — admin
    "AUDIT_ADMIN_ROLE_ASSIGNED",
    "AUDIT_ADMIN_ROLE_REVOKED",
    "AUDIT_ADMIN_TEAM_CREATED",
    "AUDIT_ADMIN_ASSET_DELETED",
    "AUDIT_ADMIN_QUOTA_CHANGED",
    # Constants — restricted / break-glass
    "AUDIT_ACCESS_RESTRICTED_ATTEMPT",
    "AUDIT_ACCESS_BREAK_GLASS_USED",
    # Constants — report
    "AUDIT_REPORT_EXPORTED",
    # Constants — Phase 3 reserved
    "AUDIT_TOKEN_ISSUED",
    "AUDIT_TOKEN_REVOKED",
    "AUDIT_TOKEN_ROTATED",
    # Constants — credential lifecycle
    "AUDIT_CREDENTIAL_CREATED",
    "AUDIT_CREDENTIAL_FAILED",
    "AUDIT_CREDENTIAL_REVOKED",
    "AUDIT_CREDENTIAL_ROTATED",
    "AUDIT_CREDENTIAL_USED",
    # Groupings
    "AUDIT_ACTIONS",
    "AUDIT_ACTIONS_SECURITY_SENSITIVE",
    # DTO
    "AuditEvent",
    # Helpers
    "is_audit_action",
    "is_security_sensitive_action",
]
