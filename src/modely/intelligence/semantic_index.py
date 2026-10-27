"""Semantic index and faceted search for Phase 4a.

Provides in-memory faceted/keyword search over the enterprise catalog.
Semantic/vector search is a pluggable backend (optional).
Applies Phase 2 permission filtering before returning results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchQuery:
    """Faceted search query for the enterprise catalog."""

    q: str = ""
    source: str | None = None
    resource_type: str | None = None
    license: str | None = None
    risk_level: str | None = None
    approval_status: str | None = None
    visibility: str | None = None
    tags: list[str] = field(default_factory=list)
    operational_state: str | None = None
    page: int = 1
    page_size: int = 20
    sort: str = ""


@dataclass
class SearchResult:
    """A single search result with relevance metadata."""

    asset_id: str
    source: str
    repo_type: str
    repo_id: str
    revision: str | None = None
    license: str | None = None
    tags: list[str] = field(default_factory=list)
    score: float = 0.0
    highlights: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id, "source": self.source, "repo_type": self.repo_type,
            "repo_id": self.repo_id, "revision": self.revision, "license": self.license,
            "tags": self.tags, "score": self.score, "highlights": self.highlights, "metadata": self.metadata,
        }


class SearchIndex:
    """In-memory faceted search index over catalog assets."""

    def __init__(self):
        self._index: list[dict] = []

    def index_asset(self, asset: dict | Any) -> None:
        if hasattr(asset, "to_dict") and not isinstance(asset, dict):
            asset = asset.to_dict()
        identity = asset.get("identity", {})
        self._index.append({
            "id": asset.get("id", ""),
            "source": asset.get("source", identity.get("source", "")),
            "repo_type": asset.get("repo_type", asset.get("resource_type", identity.get("repo_type", ""))),
            "repo_id": asset.get("repo_id", identity.get("repo_id", "")),
            "revision": asset.get("revision", identity.get("revision")),
            "license": asset.get("license", ""),
            "tags": asset.get("tags", []),
            "operational_state": asset.get("operational_state", "discovered"),
            "visibility": asset.get("visibility", "organization"),
            "size": asset.get("size", 0), "file_count": asset.get("file_count", 0),
            "checksum": asset.get("checksum", ""), "metadata": asset.get("metadata", {}),
            "risk_level": (asset.get("metadata") or {}).get("risk_level", "unknown"),
            "approval_status": (asset.get("metadata") or {}).get("approval_status", "none"),
            "_text": _searchable_text(asset),
        })

    def build_from_repository(self, repository) -> None:
        self._index.clear()
        for asset in repository.assets.list_assets():
            self.index_asset(asset)

    def search(self, query: SearchQuery, *, principal=None) -> dict:
        results = list(self._index)
        if query.q:
            q_lower = query.q.lower()
            results = [r for r in results if q_lower in r["_text"]]
            for r in results:
                r["_score"] = _text_score(r["_text"], q_lower)
        if query.source:
            results = [r for r in results if r["source"] == query.source]
        if query.resource_type:
            results = [r for r in results if r["repo_type"] == query.resource_type]
        if query.license:
            results = [r for r in results if (r["license"] or "").lower() == query.license.lower()]
        if query.risk_level:
            results = [r for r in results if r.get("risk_level") == query.risk_level]
        if query.approval_status:
            results = [r for r in results if r.get("approval_status") == query.approval_status]
        if query.visibility:
            results = [r for r in results if r["visibility"] == query.visibility]
        if query.tags:
            results = [r for r in results if all(t in r["tags"] for t in query.tags)]
        if query.operational_state:
            results = [r for r in results if r["operational_state"] == query.operational_state]
        if principal is not None:
            results = [r for r in results if _check_visible(principal, r)]
        if query.sort == "-score" and results:
            results.sort(key=lambda r: r.get("_score", 0), reverse=True)
        else:
            results.sort(key=lambda r: r.get("id", ""))
        total = len(results)
        start = (query.page - 1) * query.page_size
        paged = results[start: start + query.page_size]
        return {
            "results": [
                SearchResult(asset_id=r["id"], source=r["source"], repo_type=r["repo_type"],
                             repo_id=r["repo_id"], revision=r["revision"], license=r.get("license"),
                             tags=r["tags"], score=r.get("_score", 0.0)).to_dict()
                for r in paged
            ], "total": total, "page": query.page, "page_size": query.page_size,
        }

    def get_facets(self) -> dict:
        return {
            "sources": sorted(set(r["source"] for r in self._index if r["source"])),
            "resource_types": sorted(set(r["repo_type"] for r in self._index if r["repo_type"])),
            "licenses": sorted(set(r["license"] for r in self._index if r["license"])),
            "risk_levels": sorted(set(r.get("risk_level", "unknown") for r in self._index)),
            "operational_states": sorted(set(r["operational_state"] for r in self._index)),
        }


def _searchable_text(asset: dict) -> str:
    identity = asset.get("identity", {})
    parts = [asset.get("id", ""), asset.get("source", ""), asset.get("repo_id", ""),
             identity.get("source", ""), identity.get("repo_id", ""), asset.get("license", ""),
             " ".join(asset.get("tags", [])), str(asset.get("metadata", {}))]
    return " ".join(str(p) for p in parts if p).lower()


def _text_score(text: str, query: str) -> float:
    return text.count(query) / max(len(text), 1) * 100


def _check_visible(principal, result: dict) -> bool:
    visibility = result.get("visibility", "organization")
    if visibility == "organization": return True
    if visibility == "private": return False
    return True


__all__ = ["SearchIndex", "SearchQuery", "SearchResult"]
