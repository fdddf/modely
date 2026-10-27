"""Multi-tenant isolation middleware for enterprise API.

Provides a TenantScope injector that wraps repository queries and route
handlers so that data access is automatically scoped to the caller's
organization/workspace/project context.

Phase 2 spec: docs/specs/enterprise-multitenancy-isolation.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..domain.tenants import TenantScope


@dataclass
class TenantContext:
    """The current tenant context resolved from an authenticated principal."""

    tenant_scope: TenantScope
    principal_id: str = ""
    roles: list[str] = field(default_factory=list)

    @classmethod
    def default_org(cls, org_id: str = "default", workspace_id: str = "default") -> "TenantContext":
        """Create a default tenant context for dev/testing."""
        return cls(tenant_scope=TenantScope(organization_id=org_id, workspace_id=workspace_id))


class TenantFilteredRepository:
    """Wraps a catalog repository to enforce tenant-scoped queries.

    All list/get operations filter results by the current tenant scope.
    """

    def __init__(self, repository, tenant_context: TenantContext):
        self._repo = repository
        self._ctx = tenant_context

    @property
    def assets(self):
        return _TenantFilteredAssets(self._repo.assets, self._ctx)

    @property
    def versions(self):
        return self._repo.versions

    @property
    def files(self):
        return self._repo.files

    @property
    def jobs(self):
        return getattr(self._repo, "jobs", None)


class _TenantFilteredAssets:
    def __init__(self, assets_repo, ctx: TenantContext):
        self._assets = assets_repo
        self._ctx = ctx

    def list_assets(self):
        all_assets = list(self._assets.list_assets())
        return [a for a in all_assets if _asset_matches_tenant(a, self._ctx.tenant_scope)]

    def get_asset(self, asset_id: str):
        asset = self._assets.get_asset(asset_id)
        if asset and not _asset_matches_tenant(asset, self._ctx.tenant_scope):
            return None
        return asset

    def save_asset(self, asset):
        _set_tenant_scope(asset, self._ctx.tenant_scope)
        return self._assets.save_asset(asset)

    def delete_asset(self, asset_id: str):
        asset = self._assets.get_asset(asset_id)
        if asset and not _asset_matches_tenant(asset, self._ctx.tenant_scope):
            return
        self._assets.delete_asset(asset_id)


def _asset_matches_tenant(asset, scope: TenantScope) -> bool:
    """Check if an asset belongs to the given tenant scope."""
    asset_scope = _get_tenant_scope(asset)
    if asset_scope is None:
        return True  # No tenant scope set — visible to all
    if scope.organization_id and asset_scope.organization_id and scope.organization_id != asset_scope.organization_id:
        return False
    if scope.workspace_id and asset_scope.workspace_id and scope.workspace_id != asset_scope.workspace_id:
        return False
    return True


def _get_tenant_scope(obj: Any) -> TenantScope | None:
    if hasattr(obj, "tenant_scope") and obj.tenant_scope is not None:
        return obj.tenant_scope
    meta = getattr(obj, "metadata", {}) or {}
    ts_data = meta.get("tenant_scope")
    if ts_data:
        return TenantScope(**ts_data) if isinstance(ts_data, dict) else ts_data
    return None


def _set_tenant_scope(obj: Any, scope: TenantScope) -> None:
    """Set tenant scope on an asset object using __setattr__ for dataclass compatibility."""
    try:
        object.__setattr__(obj, "tenant_scope", scope)
    except AttributeError:
        if hasattr(obj, "metadata"):
            if obj.metadata is None:
                object.__setattr__(obj, "metadata", {})
            obj.metadata["tenant_scope"] = scope.to_dict() if hasattr(scope, "to_dict") else {"organization_id": scope.organization_id, "workspace_id": scope.workspace_id}


def apply_tenant_isolation(route_handler: Callable, tenant_ctx: TenantContext) -> Callable:
    """Wrap a route handler to inject tenant context automatically."""

    def wrapped(*args, **kwargs):
        kwargs["_tenant_ctx"] = tenant_ctx
        return route_handler(*args, **kwargs)

    return wrapped


__all__ = [
    "TenantContext",
    "TenantFilteredRepository",
    "apply_tenant_isolation",
]
