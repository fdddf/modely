"""User, team, department, role, and role-binding domain objects.

This module defines the enterprise identity objects used by governance, auth, and
tenant-scoped policy decisions.

Department is profile/reporting metadata, NOT a tenancy hierarchy level.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class User:
    """Enterprise user identity.

    ``service_account`` is a placeholder boolean for Phase 3 token/account support.
    """

    id: str
    username: str
    display_name: str = ""
    email: str = ""
    department: str = ""
    is_active: bool = True
    service_account: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Team:
    """A named group of users scoped to a tenant.

    ``tenant_scope`` links the team to a specific organization/workspace so that
    team membership and role bindings are tenant-scoped.
    """

    id: str
    name: str
    tenant_scope: str = ""  # e.g. "org:workspace"
    display_name: str = ""
    is_active: bool = True
    members: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Department:
    """Profile/reporting metadata, NOT a tenancy hierarchy level.

    Used for grouping users in reports and dashboards.  Does NOT grant or restrict
    access to assets or enforce isolation boundaries.
    """

    id: str
    name: str
    display_name: str = ""
    parent_id: str = ""
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Role:
    """A named collection of permission actions.

    Canonical roles are defined in ``governance.rbac.ROLE_ACTIONS``.
    """

    id: str
    name: str
    actions: list[str] = field(default_factory=list)
    description: str = ""
    is_builtin: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RoleBinding:
    """Assigns a role to a principal (user or team) within a scope."""

    id: str
    role_name: str
    principal_id: str  # user id or team id
    principal_type: str = "user"  # "user" or "team"
    scope: str = ""  # tenant scope, e.g. "org:workspace"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__: list[str] = [
    "User",
    "Team",
    "Department",
    "Role",
    "RoleBinding",
]
