"""CSV report formatter integration point.

Supports generic row dicts and GovernanceReport DTO section rendering
with permission-filtered, redaction-aware output.  Stable field names
are preserved.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

from ..governance.redaction import permission_filter_items


def format_csv(rows: Iterable[dict], *, fieldnames: list[str] | None = None) -> str:
    """Format dictionaries as CSV text."""
    rows = list(rows)
    if fieldnames is None:
        keys = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def format_governance_report_csv(
    report: Any,
    *,
    section: str = "assets",
    allowed_actions: set[str] | None = None,
    principal_scope: str | None = None,
) -> str:
    """Format a single section of a GovernanceReport as CSV.

    Stable sections: ``assets``, ``policy_decisions``, ``approvals``,
    ``audit_events``, ``summary``, ``metadata``.

    For ``policy_decisions`` and ``audit_events``, permission filtering
    is applied when *allowed_actions* or *principal_scope* is provided.
    """
    d = report.to_dict() if hasattr(report, "to_dict") else dict(report)

    permission_sensitive_sections = {"policy_decisions", "audit_events", "assets"}

    section_map = {
        "assets": "assets",
        "policy_decisions": "policy_decisions",
        "approvals": "approvals",
        "audit_events": "audit_events",
        "summary": "summary",
        "metadata": "metadata",
    }

    if section not in section_map:
        raise ValueError(f"Unsupported governance report section: {section}")

    key = section_map[section]
    items = d.get(key, [])

    if isinstance(items, dict):
        items = [{"key": k, "value": v} for k, v in items.items()]
    elif not isinstance(items, list):
        items = []

    # Apply permission filtering for sensitive sections
    if section in permission_sensitive_sections and (allowed_actions is not None or principal_scope is not None):
        items = permission_filter_items(
            items,
            allowed_actions=allowed_actions,
            principal_scope=principal_scope,
        )

    return format_csv(items)


__all__ = ["format_csv", "format_governance_report_csv"]
