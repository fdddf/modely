"""Admin governance API route adapters.

Admin routes require elevated permission checks (policy:manage, audit:read,
token:manage).  They delegate to injected governance/quota services and
return redacted, tenant-scoped payloads.
"""

from __future__ import annotations

from typing import Any

from ...governance.redaction import permission_filter_items, redact_credential_metadata, redact_mapping


def list_quotas(
    service: Any,
    *,
    subject: str = "",
    dimension: str = "",
    mode: str = "",
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """List quota entries, optionally filtered.

    Requires ``policy:manage`` permission.
    """
    quotas: list[dict[str, Any]] = service.list_quotas(
        subject=subject, dimension=dimension, mode=mode
    )

    # Convert to dicts and redact
    items = [q.to_dict() if hasattr(q, "to_dict") else dict(q) for q in quotas]
    items = [redact_mapping(item) for item in items]

    return {
        "data": {"quotas": items, "count": len(items)},
        "meta": {"request_id": request_id},
    }


def get_quota(
    service: Any,
    quota_id: str,
    *,
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """Get a single quota entry by id.

    Requires ``policy:manage`` permission.
    """
    quota = service.get_quota(quota_id)
    item = quota.to_dict() if hasattr(quota, "to_dict") else dict(quota)

    return {
        "data": {"quota": redact_mapping(item)},
        "meta": {"request_id": request_id},
    }


def set_quota(
    service: Any,
    payload: dict,
    *,
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """Create or update a quota entry.

    Requires ``policy:manage`` permission.
    """
    quota = service.set_quota(payload)
    item = quota.to_dict() if hasattr(quota, "to_dict") else dict(quota)

    return {
        "data": {"quota": redact_mapping(item)},
        "meta": {"request_id": request_id},
    }


def delete_quota(
    service: Any,
    quota_id: str,
    *,
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """Delete a quota entry by id.

    Requires ``policy:manage`` permission.
    """
    service.delete_quota(quota_id)

    return {
        "data": {"deleted": True, "quota_id": quota_id},
        "meta": {"request_id": request_id},
    }


def list_credentials(
    service: Any,
    *,
    source: str = "",
    tenant_scope: str = "",
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """List source credentials, optionally filtered by source or tenant scope.

    Requires ``token:manage`` permission.  Secret values are redacted.
    """
    credentials: list[Any] = service.list_credentials(
        source=source, tenant_scope=tenant_scope
    )

    # Convert to safe dicts (no secret_ref)
    items = []
    for cred in credentials:
        d = cred.to_dict() if hasattr(cred, "to_dict") else dict(cred)
        items.append(redact_credential_metadata(d))

    # Tenant-scope filter if principal is provided
    if principal is not None and hasattr(principal, "tenant_scope"):
        items = [i for i in items if i.get("tenant_scope") == principal.tenant_scope]

    return {
        "data": {"credentials": items, "count": len(items)},
        "meta": {"request_id": request_id},
    }


def get_credential(
    service: Any,
    credential_id: str,
    *,
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """Get a single credential by id (redacted).

    Requires ``token:manage`` permission.
    """
    cred = service.get_credential(credential_id)
    d = cred.to_dict() if hasattr(cred, "to_dict") else dict(cred)

    return {
        "data": {"credential": redact_credential_metadata(d)},
        "meta": {"request_id": request_id},
    }


def register_credential(
    service: Any,
    payload: dict,
    *,
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """Register a new source credential.

    Requires ``token:manage`` permission.  Returns only credential metadata
    (the secret_ref is never returned).
    """
    cred = service.register_credential(payload)
    d = cred.to_dict() if hasattr(cred, "to_dict") else dict(cred)

    return {
        "data": {"credential": redact_credential_metadata(d)},
        "meta": {"request_id": request_id},
    }


def revoke_credential(
    service: Any,
    credential_id: str,
    *,
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """Revoke a source credential by id.

    Requires ``token:manage`` permission.
    """
    cred = service.revoke_credential(credential_id)
    d = cred.to_dict() if hasattr(cred, "to_dict") else dict(cred)

    return {
        "data": {"credential": redact_credential_metadata(d)},
        "meta": {"request_id": request_id},
    }


def list_audit_events_admin(
    service: Any,
    *,
    action: str = "",
    principal_id: str = "",
    asset_id: str = "",
    since: str = "",
    until: str = "",
    request_id: str = "",
    principal: Any = None,
) -> dict[str, Any]:
    """List audit events with admin-level access.

    Requires ``audit:read`` permission.  Results are tenant-scoped and redacted.
    """
    events: list[Any] = service.list_audit_events(
        action=action,
        principal_id=principal_id,
        asset_id=asset_id,
        since=since,
        until=until,
    )

    # Convert and redact
    items = [e.to_dict() if hasattr(e, "to_dict") else dict(e) for e in events]

    # Determine allowed actions and scope from principal
    allowed_actions = None
    principal_scope = None
    if principal is not None:
        if hasattr(principal, "allowed_actions"):
            allowed_actions = set(principal.allowed_actions)
        if hasattr(principal, "tenant_scope"):
            principal_scope = principal.tenant_scope

    # Permission filter and redact
    items = permission_filter_items(
        items,
        allowed_actions=allowed_actions,
        principal_scope=principal_scope,
    )

    return {
        "data": {"audit_events": items, "count": len(items)},
        "meta": {"request_id": request_id},
    }


__all__ = [
    "delete_quota",
    "get_credential",
    "get_quota",
    "list_audit_events_admin",
    "list_credentials",
    "list_quotas",
    "register_credential",
    "revoke_credential",
    "set_quota",
]
