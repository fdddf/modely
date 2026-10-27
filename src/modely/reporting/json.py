"""JSON report formatter integration point.

Supports generic payloads, GovernanceReport DTOs, and permission-filtered
redaction-aware rendering.  Stable field names are preserved.
"""

from __future__ import annotations

import json
from typing import Any

from ..governance.redaction import permission_filter_items, redact_mapping


def format_json(payload: Any, *, indent: int = 2) -> str:
    """Format a JSON-serializable payload.

    Handles GovernanceReport DTOs, dataclasses with ``to_dict()``, plain
    dicts, and lists.  GovernanceReport.to_dict() already applies redaction.
    """
    if hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    return json.dumps(payload, indent=indent, ensure_ascii=False)


def format_governance_report_json(
    report: Any,
    *,
    indent: int = 2,
    allowed_actions: set[str] | None = None,
    principal_scope: str | None = None,
) -> str:
    """Format a GovernanceReport DTO as permission-filtered, redacted JSON.

    Args:
        report: A ``GovernanceReport`` instance (or any object with ``to_dict()``).
        indent: JSON indentation spaces.
        allowed_actions: Optional set of allowed action strings for the
            requesting principal.  When provided, list fields are filtered.
        principal_scope: Optional tenant scope for row-level filtering.
    """
    d = report.to_dict() if hasattr(report, "to_dict") else dict(report)

    # Apply permission filtering to report list fields
    if allowed_actions is not None or principal_scope is not None:
        for key in ("assets", "approvals", "audit_events", "policy_decisions", "credentials"):
            if key in d and isinstance(d[key], list):
                d[key] = permission_filter_items(
                    d[key],
                    allowed_actions=allowed_actions,
                    principal_scope=principal_scope,
                )

    return json.dumps(d, indent=indent, ensure_ascii=False)


__all__ = ["format_governance_report_json", "format_json"]
