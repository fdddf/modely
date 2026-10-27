"""Authentication route adapters."""

from __future__ import annotations

from ...governance.rbac import Principal


def get_current_principal(auth_service, token: str | None = None) -> dict:
    """Resolve the current principal through an injected auth service."""

    principal = auth_service.authenticate(token)
    return principal.to_dict() if hasattr(principal, "to_dict") else dict(principal)


def whoami(service_or_principal) -> dict:
    """Return the canonical principal details as a dictionary.

    Accepts either a ``governance.rbac.Principal`` instance or an auth
    service / adapter object with a ``get_current_principal()`` method.

    Returns a dictionary with keys:
      - ``id``: principal identifier
      - ``type``: ``"user"`` or ``"service_account"``
      - ``roles``: list of RBAC role names
      - ``tenant_scope``: optional tenant scope dict (or ``null``)
      - ``team_memberships``: list of team identifiers
      - ``correlation_id``: optional traceability identifier (or ``null``)

    Example response::

        {
            "id": "dev:admin",
            "type": "user",
            "roles": ["Platform Admin"],
            "tenant_scope": null,
            "team_memberships": ["ml-team", "platform-team"],
            "correlation_id": "req_abc123def4567890"
        }
    """
    if isinstance(service_or_principal, Principal):
        principal = service_or_principal
    elif hasattr(service_or_principal, "get_current_principal"):
        principal = service_or_principal.get_current_principal()
    else:
        raise TypeError(
            "whoami expects a Principal instance or an object with "
            "get_current_principal()"
        )

    return {
        "id": principal.id,
        "type": principal.principal_type,
        "roles": list(principal.roles),
        "tenant_scope": principal.tenant_scope.to_dict()
        if principal.tenant_scope is not None
        else None,
        "team_memberships": list(principal.team_memberships),
        "correlation_id": principal.correlation_id,
    }


__all__ = ["get_current_principal", "whoami"]
