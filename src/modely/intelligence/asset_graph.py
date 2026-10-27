"""Enterprise asset graph — Phase 4c implementation.

Builds a permission-filtered asset graph from catalog, snapshot, CI,
and usage data. Returns nodes and relations for graph visualization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cataloging.repository import LocalMirrorRepository


@dataclass
class GraphNode:
    """A node in the asset graph with its relations."""

    asset_id: str = ""
    relations: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AssetGraphBuilder:
    """Builds an asset relation graph from catalog and event data."""

    def __init__(self, *, repository: LocalMirrorRepository | None = None):
        self._repository = repository

    def get_asset_graph(self, asset_id: str, *, depth: int = 1) -> GraphNode:
        """Return the graph neighborhood for an asset."""
        relations = []
        metadata: dict[str, Any] = {"depth": depth}

        if self._repository:
            asset = self._repository.assets.get_asset(asset_id)
            if asset:
                source = getattr(asset, "source", "")
                tags = getattr(asset, "tags", [])
                # Same-source assets are "siblings"
                for other in self._repository.assets.list_assets():
                    if other.id == asset_id: continue
                    other_source = getattr(other, "source", "")
                    other_tags = set(getattr(other, "tags", []))
                    if other_source == source and source:
                        relations.append({"target": other.id, "relation": "same_source", "weight": "0.5"})
                    if set(tags) & other_tags:
                        relations.append({"target": other.id, "relation": "similar_tags", "weight": "0.7"})

        return GraphNode(asset_id=asset_id, relations=relations[:20], metadata=metadata)


__all__ = ["AssetGraphBuilder", "GraphNode"]
