"""Automated admission scoring — Phase 4b implementation.

Computes a composite admission score from license, security, approval,
reproducibility, and usage signals. Score explanations are generated for
Web display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cataloging.repository import LocalMirrorRepository


@dataclass
class AdmissionScore:
    """Composite admission score for an asset with component breakdown."""

    asset_id: str = ""
    score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id, "score": self.score,
            "components": self.components, "evidence": self.evidence,
        }


class AdmissionScorer:
    """Computes admission scores for catalog assets."""

    def __init__(self, *, repository: LocalMirrorRepository | None = None):
        self._repository = repository

    def compute_admission_score(self, asset_id: str) -> AdmissionScore:
        """Compute an admission score between 0-100."""
        if not self._repository: return AdmissionScore(asset_id=asset_id)

        asset = self._repository.assets.get_asset(asset_id)
        if asset is None: return AdmissionScore(asset_id=asset_id)

        license_score = _license_component(getattr(asset, "license", None))
        security_score = _security_component(asset)
        approval_score = _approval_component(asset)
        reproducibility_score = _reproducibility_component(asset)
        usage_score = _usage_component(asset)

        components = {
            "license": license_score,
            "security": security_score,
            "approval": approval_score,
            "reproducibility": reproducibility_score,
            "usage": usage_score,
        }
        total = sum(components.values()) / len(components)
        return AdmissionScore(asset_id=asset_id, score=round(total, 1), components=components, evidence={"components": list(components.keys())})


def _license_component(license_str: str | None) -> float:
    if not license_str: return 50.0
    license_lower = license_str.lower()
    if "apache" in license_lower or "mit" in license_lower or "bsd" in license_lower: return 100.0
    if "gpl" in license_lower or "agpl" in license_lower: return 40.0
    if "unlicensed" in license_lower: return 10.0
    return 60.0


def _security_component(asset) -> float:
    metadata = getattr(asset, "metadata", {}) or {}
    risk = metadata.get("risk_level", "unknown")
    if risk == "low": return 90.0
    if risk == "medium": return 60.0
    if risk == "high": return 30.0
    return 50.0


def _approval_component(asset) -> float:
    metadata = getattr(asset, "metadata", {}) or {}
    approval = metadata.get("approval_status", "none")
    if approval == "approved": return 100.0
    if approval == "pending": return 60.0
    if approval == "blocked": return 10.0
    return 40.0


def _reproducibility_component(asset) -> float:
    checksum = getattr(asset, "checksum", None)
    if checksum: return 80.0
    return 30.0


def _usage_component(asset) -> float:
    return 50.0  # Placeholder — enriched by analytics engine


__all__ = ["AdmissionScore", "AdmissionScorer"]
