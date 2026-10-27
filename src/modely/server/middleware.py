"""Request-scoped helpers for Phase 1b dev/basic auth and request-ID propagation.

Phase 1 auth is dev-only: ``Authorization: Bearer dev-<role>``.
No production RBAC, ACL, or credential validation is performed.
"""

from __future__ import annotations

from ..governance.rbac import Principal
from .schemas.envelopes import generate_request_id

VALID_DEV_ROLES: set[str] = {"admin", "developer", "viewer"}

# ── Dev-mode role mapping ──────────────────────────────────────────────────
# Maps dev auth tokens to canonical RBAC role names and principal types.
_DEV_ROLE_TO_RBAC: dict[str, tuple[str, str]] = {
    "admin": ("Platform Admin", "user"),
    "developer": ("Developer", "user"),
    "viewer": ("Viewer", "user"),
}


def extract_request_id(headers: dict[str, str] | None = None) -> str:
    """Return an existing ``X-Request-ID`` header value or generate a new one."""
    if headers and "X-Request-ID" in headers:
        return headers["X-Request-ID"]
    if headers and "x-request-id" in headers:
        return headers["x-request-id"]
    return generate_request_id()


def parse_dev_auth(headers: dict[str, str] | None = None) -> Principal | None:
    """Parse a ``dev-<role>`` bearer token for Phase 1 placeholder auth.

    Returns ``None`` when no Authorization header is present (unauthenticated).
    Falls back to ``viewer`` when the role is unrecognised.

    The returned principal is a ``governance.rbac.Principal`` with:
    - ``id``: ``"dev:<role>"``
    - ``roles``: the canonical RBAC role name (e.g. ``"Platform Admin"``)
    - ``principal_type``: ``"user"`` (dev-mode always maps to human users)
    - ``team_memberships``: resolved from the ``X-Dev-Teams`` header if
      present (comma-separated team identifiers)
    - ``correlation_id``: request id from ``X-Request-ID`` header for
      traceability
    - ``metadata``: ``{"auth_mode": "dev_basic", "token_prefix": "dev-"}``
    """

    if not headers:
        return None
    auth = headers.get("Authorization", headers.get("authorization", ""))
    if not auth:
        return None

    # Only accept Bearer tokens in Phase 1 dev mode
    if not auth.lower().startswith("bearer "):
        return None

    token = auth[7:].strip()  # len("Bearer ") == 7
    if not token:
        return None

    role = "viewer"
    if token.startswith("dev-"):
        candidate = token.removeprefix("dev-")
        if candidate in VALID_DEV_ROLES:
            role = candidate

    rbac_role, principal_type = _DEV_ROLE_TO_RBAC.get(role, ("Viewer", "user"))

    # ── Resolve team memberships from dev header ───────────────────────────
    team_memberships: list[str] = []
    teams_header = headers.get("X-Dev-Teams", headers.get("x-dev-teams", ""))
    if teams_header:
        team_memberships = [t.strip() for t in teams_header.split(",") if t.strip()]

    # ── Resolve correlation_id from request id header ──────────────────────
    correlation_id = extract_request_id(headers)

    return Principal(
        id=f"dev:{role}",
        roles=[rbac_role],
        principal_type=principal_type,
        team_memberships=team_memberships,
        correlation_id=correlation_id,
        metadata={
            "auth_mode": "dev_basic",
            "token_prefix": "dev-",
        },
    )


__all__ = ["VALID_DEV_ROLES", "extract_request_id", "parse_dev_auth"]
