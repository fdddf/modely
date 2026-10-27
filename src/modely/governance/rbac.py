"""Role-based access control helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .permissions import DEFAULT_ACTIONS, PermissionDecision, allow

if TYPE_CHECKING:
    from ..domain.tenants import TenantScope

ROLE_ACTIONS = {
    "Platform Admin": DEFAULT_ACTIONS,
    "Security Admin": {
        "asset:read", "asset:scan", "asset:approve", "asset:manage_acl",
        "policy:manage", "audit:read", "report:read",
    },
    "Asset Admin": {
        "asset:read", "asset:download", "asset:sync", "asset:publish",
        "asset:delete", "asset:scan", "report:read",
    },
    "Team Admin": {
        "asset:read", "asset:download", "asset:sync", "asset:publish",
        "asset:scan", "report:read",
    },
    "Developer": {"asset:read", "asset:download", "asset:scan"},
    "Viewer": {"asset:read"},
    "Service Account": {
        "asset:read", "asset:download", "asset:sync", "asset:scan",
        "token:manage",
    },
}


@dataclass
class Principal:
    """Subject used by RBAC checks and auth middleware.

    ``id`` is the unique identifier for the principal (e.g. username, user
    uuid, or ``dev:<role>`` in dev mode).

    ``roles`` are the bound RBAC role names (e.g. "Developer", "Platform
    Admin").  Roles are unioned during permission evaluation.

    ``principal_type`` distinguishes human users (``"user"``) from
    non-human service accounts (``"service_account"``).  Service accounts
    follow a restricted role matrix and may carry a ``correlation_id`` for
    traceability.

    ``tenant_scope`` is optional; when set it scopes the principal to a
    specific organization/workspace for multi-tenant policy evaluation.

    ``team_memberships`` carries the set of team identifiers the principal
    belongs to.  Used by visibility checks at the ``team`` visibility level
    (see ``cataloging.visibility.check_visibility``).

    ``correlation_id`` is an optional traceability identifier (typically a
    request id) that links a service-account action back to a user-facing
    operation.
    """

    id: str
    roles: list[str] = field(default_factory=list)
    principal_type: str = "user"  # "user" or "service_account"
    tenant_scope: TenantScope | None = None
    team_memberships: list[str] = field(default_factory=list)
    correlation_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to a dictionary suitable for serialization and policy
        evaluation.  Fields that are ``None`` are omitted from the output.
        """
        d: dict = {
            "id": self.id,
            "roles": list(self.roles),
            "principal_type": self.principal_type,
            "tenant_scope": self.tenant_scope.to_dict() if self.tenant_scope is not None else None,
            "team_memberships": list(self.team_memberships),
            "metadata": dict(self.metadata),
        }
        if self.correlation_id is not None:
            d["correlation_id"] = self.correlation_id
        return d


def check_permission(
    principal: Principal,
    action: str,
    *,
    resource: object | None = None,
    tenant_scope: TenantScope | None = None,
) -> PermissionDecision:
    """Evaluate an action against a principal's role matrix.

    Decision precedence (highest to lowest):

    1. **Explicit DENY on the resource** — if the resource carries an ACL
       or explicit deny list and the principal is target-flagged, deny
       immediately regardless of roles.  (Currently informational; full
       resource ACLs are planned for Phase 3+.)

    2. **TenantScope mismatch** — when a *resource* is provided and has a
       ``tenant_scope`` attribute, the principal's tenant_scope must
       overlap the resource's scope.  Mismatched organizations or
       workspaces result in deny before role evaluation.  When
       *tenant_scope* is passed directly (no resource), it is checked
       against the principal's scope in the same way.

    3. **Role-based ALLOW** — the union of all role-granted actions is
       computed.  If *action* is present in the union and no higher-
       priority rule has denied it, the action is allowed.

    4. **Default DENY** — any action not explicitly granted by a role is
       denied.

    Backward compatibility: existing callers that pass only ``(principal,
    action)`` continue to work unchanged.  The new ``resource`` and
    ``tenant_scope`` keyword-only arguments are optional.
    """
    # ── 2a. TenantScope mismatch (resource-level) ──────────────────────────
    if resource is not None:
        resource_scope = getattr(resource, "tenant_scope", None)
        if resource_scope is not None and principal.tenant_scope is not None:
            if principal.tenant_scope.organization_id != resource_scope.organization_id:
                decision = PermissionDecision(False, action, "tenant_scope_mismatch")
                decision.metadata["principal_id"] = principal.id
                decision.metadata["roles"] = list(principal.roles)
                if principal.tenant_scope is not None:
                    decision.metadata["tenant_scope"] = principal.tenant_scope
                decision.metadata["resource_tenant_scope"] = resource_scope
                return decision

    # ── 2b. TenantScope mismatch (explicit tenant_scope arg) ───────────────
    if tenant_scope is not None and principal.tenant_scope is not None:
        if principal.tenant_scope.organization_id != tenant_scope.organization_id:
            decision = PermissionDecision(False, action, "tenant_scope_mismatch")
            decision.metadata["principal_id"] = principal.id
            decision.metadata["roles"] = list(principal.roles)
            decision.metadata["tenant_scope"] = principal.tenant_scope
            decision.metadata["requested_tenant_scope"] = tenant_scope
            return decision

    # ── 3. Role-based evaluation ───────────────────────────────────────────
    allowed_actions = set()
    for role in principal.roles:
        allowed_actions.update(ROLE_ACTIONS.get(role, set()))
    decision = allow(action, allowed_actions=allowed_actions)
    decision.metadata["principal_id"] = principal.id
    decision.metadata["roles"] = list(principal.roles)
    if principal.tenant_scope is not None:
        decision.metadata["tenant_scope"] = principal.tenant_scope
    # ── 4. Default deny is implicit via allow() returning False ────────────
    return decision


__all__ = ["ROLE_ACTIONS", "Principal", "check_permission"]
