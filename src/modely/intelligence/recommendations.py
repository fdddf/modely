"""Similar asset recommendation helpers — Phase 4b implementation.

Generates recommendations based on tag similarity, license compatibility,
and usage patterns. Recommends approved alternatives for blocked/high-risk assets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cataloging.repository import LocalMirrorRepository


@dataclass
class Recommendation:
    """A recommendation for a similar or alternative asset."""

    asset_id: str = ""
    reason: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RecommendationEngine:
    """In-memory recommendation engine using tag/license/usage similarity."""

    def __init__(self, *, repository: LocalMirrorRepository | None = None, search_index=None):
        self._repository = repository
        self._search_index = search_index

    def get_recommendations(self, asset_id: str, *, limit: int = 5) -> list[Recommendation]:
        """Return similar assets based on tag overlap."""
        if not self._repository: return []
        source_asset = self._repository.assets.get_asset(asset_id)
        if source_asset is None: return []
        source_tags = set(source_asset.tags if hasattr(source_asset, "tags") else [])
        source_license = getattr(source_asset, "license", None)

        scored = []
        for other in self._repository.assets.list_assets():
            if other.id == asset_id: continue
            other_tags = set(getattr(other, "tags", []))
            overlap = len(source_tags & other_tags)
            if overlap > 0:
                score = overlap / max(len(source_tags | other_tags), 1)
                reason = f"Shares {overlap} tags"
                if source_license and getattr(other, "license", None) == source_license:
                    reason += " and same license"
                    score += 0.1
                scored.append((score, other, reason))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [Recommendation(asset_id=s[1].id, reason=s[2], confidence=min(s[0], 1.0)) for s in scored[:limit]]

    def get_alternatives(self, asset_id: str, *, limit: int = 5) -> list[Recommendation]:
        """Return approved alternatives (same resource_type, different source, approved)."""
        if not self._repository: return []
        source_asset = self._repository.assets.get_asset(asset_id)
        if source_asset is None: return []

        source_type = getattr(source_asset, "repo_type", "") or source_asset.identity.repo_type if hasattr(source_asset, "identity") else ""
        source_tags = set(getattr(source_asset, "tags", []))

        alts = []
        for other in self._repository.assets.list_assets():
            if other.id == asset_id: continue
            other_type = getattr(other, "repo_type", "") or (other.identity.repo_type if hasattr(other, "identity") else "")
            if other_type != source_type: continue
            if getattr(other, "operational_state", "") != "synced": continue

            other_tags = set(getattr(other, "tags", []))
            overlap = len(source_tags & other_tags)
            confidence = overlap / max(len(source_tags), 1) if source_tags else 0.1
            alts.append(Recommendation(asset_id=other.id, reason=f"Same type '{source_type}'" + (f", shares {overlap} tags" if overlap else ""), confidence=min(confidence, 1.0)))

        alts.sort(key=lambda r: r.confidence, reverse=True)
        return alts[:limit]


__all__ = ["Recommendation", "RecommendationEngine"]
