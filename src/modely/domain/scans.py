"""Scan report domain objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..types import ScanFinding, ScanResult

SCAN_SEVERITIES: tuple[str, ...] = ("info", "low", "medium", "high", "critical")
RISK_LEVELS: tuple[str, ...] = ("unknown", "low", "medium", "high", "critical")


@dataclass
class ScanSummary:
    """Stable summary of scan findings for catalog and policy surfaces."""

    risk_level: str = "unknown"
    counts: dict[str, int] = field(default_factory=dict)
    finding_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"Unsupported risk level: {self.risk_level}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_scan_severity(value: str) -> bool:
    return value in SCAN_SEVERITIES


__all__ = [
    "RISK_LEVELS",
    "SCAN_SEVERITIES",
    "ScanFinding",
    "ScanResult",
    "ScanSummary",
    "is_scan_severity",
]
