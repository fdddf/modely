"""Cost optimization suggestions — Phase 4c implementation.

Generates cost recommendations based on storage size and usage patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CostRecommendation:
    """A cost optimization recommendation."""

    asset_id: str = ""
    category: str = ""
    estimated_savings: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "category": self.category, "estimated_savings": self.estimated_savings, "reason": self.reason, "metadata": self.metadata}


class CostAnalyzer:
    """Generates cost optimization recommendations from catalog data."""

    def get_cost_recommendations(self, *, repository=None, analytics_engine=None) -> list[CostRecommendation]:
        recommendations = []
        if not repository: return recommendations

        for asset in repository.assets.list_assets():
            size = getattr(asset, "size", 0) or 0
            file_count = getattr(asset, "file_count", 0) or 0
            state = getattr(asset, "operational_state", "")

            if size > 10_000_000_000:  # > 10GB
                recommendations.append(CostRecommendation(asset_id=asset.id, category="large_asset", estimated_savings="~$X/month", reason=f"Large asset ({size // 1_000_000_000}GB) — consider tiering to cold storage"))
            if state == "archived" and size > 0:
                recommendations.append(CostRecommendation(asset_id=asset.id, category="archived_storage", estimated_savings="~$X/month", reason="Archived asset still consuming storage — consider cleanup"))

        return recommendations


__all__ = ["CostAnalyzer", "CostRecommendation"]
