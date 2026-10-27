"""Governance API schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PolicyDecisionResponse:
    outcome: str
    reasons: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovalResponse:
    id: str
    asset_id: str
    status: str
    requester: str | None = None
    reviewer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["ApprovalResponse", "PolicyDecisionResponse"]
