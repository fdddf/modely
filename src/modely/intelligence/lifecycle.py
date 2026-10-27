"""Lifecycle governance suggestions — Phase 4c implementation.

Detects stale assets and generates lifecycle recommendations based on
usage patterns, age, and policy decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LifecycleSuggestion:
    """A lifecycle governance suggestion for an asset."""

    asset_id: str = ""
    action: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "action": self.action, "reason": self.reason, "metadata": self.metadata}


class LifecycleGovernance:
    """Generates lifecycle governance suggestions from usage and age data."""

    def get_stale_assets(self, *, analytics_engine=None, threshold_days: int = 90) -> list[str]:
        if analytics_engine:
            return analytics_engine.get_stale_assets(threshold_days=threshold_days)
        return []

    def get_lifecycle_suggestions(self, *, analytics_engine=None, repository=None) -> list[LifecycleSuggestion]:
        suggestions = []
        stale = self.get_stale_assets(analytics_engine=analytics_engine)
        for asset_id in stale:
            suggestions.append(LifecycleSuggestion(asset_id=asset_id, action="archive_candidate", reason=f"No usage in 90+ days"))

        if repository:
            for asset in repository.assets.list_assets():
                state = getattr(asset, "operational_state", "")
                if state == "failed":
                    suggestions.append(LifecycleSuggestion(asset_id=asset.id, action="cleanup_candidate", reason="Sync failed"))

        return suggestions


__all__ = ["LifecycleGovernance", "LifecycleSuggestion"]
