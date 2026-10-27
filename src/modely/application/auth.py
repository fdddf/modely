"""Application-level auth service.

Handles principal resolution, dev-mode user seeding, and provides
documented integration points for OIDC/LDAP in later phases.

Integration points (Phase 3+):
  - ``resolve_principal`` should be extended to consult an external identity
    provider (OIDC IdP or LDAP directory) after local dev users are checked.
  - OIDC/LDAP callbacks should populate ``governance.rbac.Principal`` with
    roles derived from group/claim mappings.
  - Service account tokens (Phase 3) will be validated against a token
    registry keyed by ``token_id``.
"""

from __future__ import annotations

from typing import Optional

from ..domain.users import User
from ..governance.rbac import Principal

# Local dev-mode user store seeded by ``seed_local_users``.
_LOCAL_USERS: dict[str, User] = {}
_LOCAL_PRINCIPALS: dict[str, Principal] = {}


def resolve_principal(
    username: str,
    *,
    token: str | None = None,
) -> Principal | None:
    """Resolve a principal from the dev-mode user store.

    In dev mode this consults locally seeded users.  In production (Phase 3+)
    this will fall through to an OIDC provider or LDAP directory.

    Args:
        username: The username (or bearer token subject) to look up.
        token: Optional bearer token; reserved for Phase 3 service-account
               token validation.

    Returns:
        A ``Principal`` if found, otherwise ``None`` (treat as unauthenticated).
    """
    principal = _LOCAL_PRINCIPALS.get(username)

    # ── Audit: user.login / user.login_failed ────────────────────────────
    from ..domain.audit_events import AUDIT_AUTH_LOGIN, AUDIT_AUTH_LOGIN_FAILED
    from ..governance.audit import emit_audit_event

    if principal is not None:
        emit_audit_event(
            AUDIT_AUTH_LOGIN,
            resource=username,
            status="ok",
            actor=principal.id,
            metadata={
                "username": username,
                "roles": principal.roles,
            },
        )
    else:
        emit_audit_event(
            AUDIT_AUTH_LOGIN_FAILED,
            resource=username,
            status="denied",
            metadata={
                "username": username,
                "has_token": token is not None,
            },
        )

    return principal


def seed_local_users(users: list[dict]) -> None:
    """Seed the dev-mode user store with test users.

    Each dict must contain ``id``, ``username``, and optionally ``roles``
    (list of role name strings), ``display_name``, ``email``, ``department``,
    and ``service_account``.

    ``roles`` are mapped to ``governance.rbac.Principal`` records.

    Example::

        seed_local_users([
            {"id": "u1", "username": "alice", "display_name": "Alice",
             "roles": ["Platform Admin"]},
            {"id": "u2", "username": "bob", "roles": ["Developer"]},
        ])

    OIDC/LDAP integration point: in Phase 3 this function will be replaced by
    an identity provider connector that syncs users and role bindings from the
    external directory into ``_LOCAL_PRINCIPALS``.
    """
    for entry in users:
        user = User(
            id=entry["id"],
            username=entry["username"],
            display_name=entry.get("display_name", ""),
            email=entry.get("email", ""),
            department=entry.get("department", ""),
            service_account=entry.get("service_account", False),
        )
        _LOCAL_USERS[user.username] = user

        roles = entry.get("roles", [])
        principal = Principal(
            id=user.id,
            roles=roles if roles else ["Viewer"],
            metadata={"username": user.username, "display_name": user.display_name},
        )
        _LOCAL_PRINCIPALS[user.username] = principal


def _clear_local_store() -> None:
    """Clear the dev-mode user store (used in tests)."""
    _LOCAL_USERS.clear()
    _LOCAL_PRINCIPALS.clear()


__all__ = [
    "resolve_principal",
    "seed_local_users",
    # re-exported from modely.auth
    "get_token",
    "save_token",
    "delete_token",
    "has_token",
    "whoami",
]
