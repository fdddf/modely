"""Governance report domain helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .redaction import redact_mapping


@dataclass
class GovernanceReport:
    """Minimal governance report DTO before format-specific rendering."""

    title: str
    assets: list[dict[str, Any]] = field(default_factory=list)
    policy_decisions: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return redact_mapping(asdict(self))


def build_governance_report(title: str, **sections) -> GovernanceReport:
    """Build a redaction-aware governance report DTO."""

    return GovernanceReport(title=title, **sections)


__all__ = ["GovernanceReport", "build_governance_report"]
