"""Intelligence API schemas for Phase 4 enterprise API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# -- Search schemas (4a) -------------------------------------------------------

@dataclass
class SearchRequest:
    """Search query parameters."""

    q: str = ""
    source: str | None = None
    resource_type: str | None = None
    license: str | None = None
    risk_level: str | None = None
    approval_status: str | None = None
    visibility: str | None = None
    tags: str | None = None
    operational_state: str | None = None
    page: int = 1
    page_size: int = 20
    sort: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResultItem:
    """A single search result."""

    asset_id: str = ""
    source: str = ""
    repo_type: str = ""
    repo_id: str = ""
    revision: str | None = None
    license: str | None = None
    tags: list[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    """Response from a search query."""

    results: list[SearchResultItem] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    facets: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"results": [r.to_dict() for r in self.results], "total": self.total, "page": self.page, "page_size": self.page_size, "facets": self.facets}


# -- Analytics schemas (4a) ----------------------------------------------------

@dataclass
class RiskTrendsResponse:
    """Risk trend analytics response."""

    period: str = ""
    total_findings: int = 0
    high_severity: int = 0
    medium_severity: int = 0
    low_severity: int = 0
    trend_direction: str = "stable"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UsagePopularityResponse:
    """Usage popularity analytics response."""

    assets: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Recommendations schemas (4b) ----------------------------------------------

@dataclass
class Recommendation:
    """A recommendation for a similar or alternative asset."""

    asset_id: str = ""
    reason: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationsResponse:
    """Response with recommendations for an asset."""

    asset_id: str = ""
    recommendations: list[Recommendation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "recommendations": [r.to_dict() for r in self.recommendations]}


@dataclass
class AdmissionScoreResponse:
    """Admission score for an asset."""

    asset_id: str = ""
    score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Compliance schemas (4c) ---------------------------------------------------

@dataclass
class ComplianceReportResponse:
    """Compliance report response."""

    title: str = ""
    generated_at: str = ""
    format: str = "json"
    summary: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Graph schema (4c) ---------------------------------------------------------

@dataclass
class AssetGraphNode:
    """A node in the asset graph."""

    asset_id: str = ""
    relations: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "AdmissionScoreResponse",
    "AssetGraphNode",
    "ComplianceReportResponse",
    "Recommendation",
    "RecommendationsResponse",
    "RiskTrendsResponse",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "UsagePopularityResponse",
]
