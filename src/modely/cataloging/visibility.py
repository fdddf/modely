"""Catalog visibility filtering helpers.

Controls which assets a principal can discover based on tenant scope and
visibility labels.  Policy decisions (allow/block) are evaluated separately
by the policy engine; visibility is purely about discovery / listing.

Visibility states (6 levels, per docs/specs/enterprise-domain-model.md):
- ``organization``: visible to any principal in the same organization.
- ``workspace``: visible to principals in the same org + workspace.
- ``team``: visible to principals in the same org + workspace + team.
- ``project``: visible to principals in the same org + workspace + project.
- ``private``: visible only to the resource owner or platform admins.
- ``restricted``: visible only to explicitly authorized principals.

"blocked" is a policy outcome, NOT a visibility value.  The domain model
enforces this at Asset construction via ``VISIBILITY_LEVELS`` — constructing
an Asset with visibility="blocked" raises ValueError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.tenants import TenantScope
    from ..governance.rbac import Principal

# Canonical visibility labels (per docs/specs/enterprise-domain-model.md).
# Note: "blocked" is explicitly excluded — it is a policy_decision outcome.
_VISIBILITY_LEVELS: frozenset[str] = frozenset([
    "organization",
    "workspace",
    "team",
    "project",
    "private",
    "restricted",
])

_PLATFORM_SCOPES = {"organization", "workspace", "team", "project"}


def is_valid_visibility(value: str) -> bool:
    """Return whether ``value`` is a valid visibility level.

    "blocked" will always return ``False`` here — it is a policy outcome,
    never a visibility value.
    """
    return value in _VISIBILITY_LEVELS


def check_visibility(
    principal: "Principal | None",
    resource: object,
) -> bool:
    """Check whether a principal can discover a resource based on visibility
    and tenant scope.

    Visibility rules:
    - ``organization``: visible to any principal in the same organization.
    - ``workspace``: visible to principals in the same org + workspace.
    - ``team``: visible to principals in the same org + workspace + team.
    - ``project``: visible to principals in the same org + workspace + project.
    - ``private``: visible only to the resource owner or platform admins.
    - ``restricted``: visible only to explicitly authorized principals.

    If the principal is ``None`` (unauthenticated), nothing is discoverable.

    Returns ``True`` if the principal can discover the resource.
    """
    # Unauthenticated: can't discover anything
    if principal is None:
        return False

    # Platform Admins can discover everything
    if "Platform Admin" in principal.roles:
        return True

    # Get visibility from the resource
    visibility = getattr(resource, "visibility", None)
    if visibility is None:
        return False

    # Guard: "blocked" must never be treated as a visibility value
    if visibility not in _VISIBILITY_LEVELS:
        return False

    # Get tenant scopes
    principal_scope: TenantScope | None = getattr(principal, "tenant_scope", None)
    resource_scope: TenantScope | None = getattr(resource, "tenant_scope", None)

    # private: only visible if principal owns the resource
    if visibility == "private":
        resource_owner = getattr(resource, "owner_principal_id", None)
        return resource_owner is not None and resource_owner == principal.id

    # restricted: requires explicit auth — deny by default, allowlist
    if visibility == "restricted":
        authorized_principals = getattr(resource, "authorized_principals", frozenset())
        return principal.id in authorized_principals

    # Scoped visibility (organization, workspace, team, project)
    if visibility in _PLATFORM_SCOPES:
        if principal_scope is None:
            return False
        if resource_scope is None:
            # Default: require same org + workspace when no resource scope
            return True

        # Must share the same organization
        if principal_scope.organization_id != resource_scope.organization_id:
            return False

        # workspace-level: also must share workspace
        if visibility in {"workspace", "team", "project"}:
            if principal_scope.workspace_id != resource_scope.workspace_id:
                return False

        # team-level: also must share team
        if visibility == "team":
            principal_team = getattr(principal, "team_id", None)
            resource_team = getattr(resource, "team_id", None)
            if resource_team is None:
                meta = getattr(resource, "metadata", None) or {}
                resource_team = meta.get("team_id")
            if principal_team and resource_team and principal_team != resource_team:
                return False

        # project-level: also must share project
        if visibility == "project":
            if principal_scope.project_id is not None and resource_scope.project_id is not None:
                if principal_scope.project_id != resource_scope.project_id:
                    return False

        return True

    # Unknown visibility — deny
    return False


__all__ = ["check_visibility", "is_valid_visibility"]
