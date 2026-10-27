"""Tenant, organization, workspace, project, and environment domain objects.

These are the canonical tenancy hierarchy entities used by the enterprise platform.
TenantScope is the canonical value object for scoping entities, policies, and
permission checks to a specific organization and workspace.  Every tenant-scoped
operation MUST carry a TenantScope with at least ``organization_id`` and
``workspace_id``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TenantScope:
    """Shared value object for tenant-scoped entities and authorization decisions.

    ``organization_id`` and ``workspace_id`` are always required.
    ``project_id`` and ``environment_id`` are optional for finer-grained scoping.
    """

    organization_id: str
    workspace_id: str
    project_id: str | None = None
    environment_id: str | None = None

    def __post_init__(self) -> None:
        if not self.organization_id:
            raise ValueError("TenantScope requires organization_id")
        if not self.workspace_id:
            raise ValueError("TenantScope requires workspace_id")

    @property
    def org_id(self) -> str:
        """Convenience alias for organization_id."""
        return self.organization_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Organization:
    """Top-level tenancy container representing a company or business unit."""

    id: str
    name: str
    display_name: str = ""
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Workspace:
    """A workspace bound to one organization, grouping projects and resources."""

    id: str
    organization_id: str
    name: str
    display_name: str = ""
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Project:
    """An optional project within a workspace for finer-grained grouping."""

    id: str
    workspace_id: str
    name: str
    display_name: str = ""
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Environment:
    """A deployment or execution environment within a project (dev, staging, prod, etc.)."""

    id: str
    name: str
    display_name: str = ""
    project_id: str | None = None
    workspace_id: str | None = None
    organization_id: str | None = None
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "Environment",
    "Organization",
    "Project",
    "TenantScope",
    "Workspace",
]
