"""Enterprise authorization context.

``AuthContext`` is the canonical authorization value-object for all Phase 4
intelligence functions.  It is constructed from the Phase 2 ``Principal``
dev/basic-auth placeholder plus a ``TenantScope`` and RBAC permissions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .tenants import TenantScope


@dataclass
class AuthContext:
    """Canonical caller identity + scope for enterprise intelligence functions.

    Every Phase 4 function that performs permission filtering, ranking, or
    visibility checks accepts an ``AuthContext``.
    """

    principal_id: str
    role: str
    tenant_scope: TenantScope
    permissions: set[str] = field(default_factory=set)
    team_bindings: list[str] = field(default_factory=list)
    auth_mode: str = "dev_basic"
    request_id: str | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_principal(
        cls,
        principal,  # server.schemas.envelopes.Principal (avoid circular import)
        tenant_scope: TenantScope,
        permissions: set[str] | None = None,
    ) -> AuthContext:
        """Build an ``AuthContext`` from a Phase-2 dev ``Principal``.

        This bridges the Phase 2 placeholder auth model (which only carries
        ``id``, ``role``, and ``labels``) with the richer Phase 4 context
        required by permission-filtered search, recommendations, graph
        traversal, and reports.
        """
        return cls(
            principal_id=principal.id,
            role=principal.role,
            tenant_scope=tenant_scope,
            permissions=permissions or set(),
            team_bindings=principal.labels.get("teams", []),
            auth_mode=principal.labels.get("auth_mode", "dev_basic"),
        )


__all__ = ["AuthContext"]
