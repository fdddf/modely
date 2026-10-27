"""Sensitive field redaction helpers.

Includes credential metadata redaction for audit logs, reports, and
permission-filtered data views.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_FIELD_NAMES = {
    "token",
    "access_token",
    "api_token",
    "authorization",
    "password",
    "secret",
    "private_key",
    "credential",
    "secret_ref",
}
REDACTION = "<redacted>"
_TOKEN_PATTERN = re.compile(r"(?i)(token|secret|password|api[_-]?key)=([^\s&]+)")

# Credential fields that may be included in reports/logs (never secret_ref)
_CREDENTIAL_SAFE_FIELDS = {
    "id",
    "tenant_scope",
    "source",
    "credential_type",
    "owner",
    "allowed_actions",
    "created_at",
    "rotated_at",
    "expires_at",
    "revoked_at",
    "last_used_at",
    "metadata",
}

# Fields to strip from credential objects rendered in reports
_CREDENTIAL_STRIP_FIELDS = {
    "secret_ref",
    "owner_principal",
    "owner_team",
}


def is_sensitive_field(name: str) -> bool:
    lowered = name.lower()
    return lowered in SENSITIVE_FIELD_NAMES or any(part in lowered for part in ("token", "secret", "password", "private_key"))


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _TOKEN_PATTERN.sub(lambda match: f"{match.group(1)}={REDACTION}", value)
    return value


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if is_sensitive_field(str(key)):
            redacted[key] = REDACTION
        elif isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [redact_mapping(item) if isinstance(item, Mapping) else redact_value(item) for item in value]
        else:
            redacted[key] = redact_value(value)
    return redacted


def redact_credential_metadata(credential_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact credential metadata for safe inclusion in audit logs and reports.

    Strips secret_ref and deprecated owner fields, returning only safe metadata.
    """
    safe: dict[str, Any] = {}
    for key, value in credential_dict.items():
        if key in _CREDENTIAL_STRIP_FIELDS:
            continue
        if is_sensitive_field(key):
            safe[key] = REDACTION
        else:
            safe[key] = value
    return safe


def permission_filter_items(
    items: list[dict[str, Any]],
    *,
    allowed_actions: set[str] | None = None,
    principal_scope: str | None = None,
) -> list[dict[str, Any]]:
    """Filter and redact items based on principal permissions.

    Args:
        items: List of item dicts to filter.
        allowed_actions: Set of allowed action strings for the principal.
            Items with an ``action`` field not in this set are removed.
        principal_scope: Optional tenant scope string. Items scoped outside
            this scope are removed when provided.

    Returns:
        Filtered and redacted list.
    """
    filtered: list[dict[str, Any]] = []
    for item in items:
        # Permission-based filtering
        if allowed_actions is not None and "action" in item:
            if item["action"] not in allowed_actions:
                continue

        # Tenant scope filtering
        if principal_scope and "tenant_scope" in item:
            if item["tenant_scope"] != principal_scope:
                continue

        # Redact any sensitive fields
        filtered.append(redact_mapping(item))
    return filtered


__all__ = [
    "REDACTION",
    "SENSITIVE_FIELD_NAMES",
    "is_sensitive_field",
    "permission_filter_items",
    "redact_credential_metadata",
    "redact_mapping",
    "redact_value",
]
