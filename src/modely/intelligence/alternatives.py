"""Approved alternatives lookup — Phase 4b/4c integration."""

from __future__ import annotations

from ..cataloging.repository import LocalMirrorRepository
from .recommendations import Recommendation, RecommendationEngine


class AlternativesLookup:
    """Finds approved alternatives for blocked or high-risk assets."""

    def __init__(self, *, repository: LocalMirrorRepository | None = None):
        self._engine = RecommendationEngine(repository=repository)

    def get_alternatives(self, asset_id: str, *, limit: int = 5) -> list[Recommendation]:
        return self._engine.get_alternatives(asset_id, limit=limit)


__all__ = ["AlternativesLookup"]
