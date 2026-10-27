"""Enterprise intelligence application services.

Shared use-case layer for CLI, server routes, and tests.  Every function
accepts Protocol-backed dependencies so callers can inject test doubles
without coupling to concrete repositories or network calls.
"""

from __future__ import annotations

from typing import Any

from ..domain.auth import AuthContext
from ..domain.tenants import TenantScope


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_catalog(
    query: str,
    *,
    auth_context: AuthContext | None = None,
    source: str | None = None,
    resource_type: str | None = None,
    license_filter: str | None = None,
    risk_level: str | None = None,
    tags: str | None = None,
    sort: str = "-updated_at",
    page: int = 1,
    page_size: int = 20,
    include: str | None = None,
    **_filters: Any,
) -> dict[str, Any]:
    """Search the enterprise catalog with faceted filters.

    When the full intelligence search backend is available this delegates
    to :func:`modely.intelligence.semantic_index.execute_search`.  For now
    it returns a well-formed empty result so CLI and server code can be
    written and tested against it.
    """
    # TODO: delegate to intelligence.semantic_index.execute_search(...)
    return {
        "results": [],
        "total": 0,
        "facets": {},
        "_status": "placeholder",
    }


# ---------------------------------------------------------------------------
# Recommendations & alternatives
# ---------------------------------------------------------------------------


def get_recommendations(
    asset_id: str,
    *,
    auth_context: AuthContext | None = None,
    top_k: int = 5,
    min_confidence: float = 0.3,
) -> dict[str, Any]:
    """Return similar-asset recommendations for *asset_id*."""
    # TODO: delegate to intelligence.recommendations.recommend_similar_assets(...)
    return {
        "asset_id": asset_id,
        "recommendations": [],
        "reason": "no_similar_found" if top_k else "not_applicable",
        "_status": "placeholder",
    }


def get_alternatives(
    asset_id: str,
    *,
    auth_context: AuthContext | None = None,
    top_k: int = 5,
    only_when_blocked: bool = True,
) -> dict[str, Any]:
    """Return approved alternatives for a blocked or high-risk *asset_id*."""
    # TODO: delegate to intelligence.alternatives.recommend_approved_alternatives(...)
    return {
        "asset_id": asset_id,
        "alternatives": [],
        "reason": "not_applicable" if only_when_blocked else "no_alternatives_found",
        "_status": "placeholder",
    }


# ---------------------------------------------------------------------------
# Admission scoring
# ---------------------------------------------------------------------------


def get_admission_score(
    asset_id: str,
    *,
    auth_context: AuthContext | None = None,
    profile_override: str | None = None,
) -> dict[str, Any]:
    """Compute the enterprise admission score for *asset_id*."""
    # TODO: delegate to intelligence.admission_score.compute_admission_score(...)
    return {
        "asset_id": asset_id,
        "overall_score": 0,
        "grade": "N/A",
        "dimensions": {},
        "scoring_version": "0.0.0-placeholder",
        "_status": "placeholder",
    }


# ---------------------------------------------------------------------------
# Asset graph
# ---------------------------------------------------------------------------


def get_asset_graph(
    asset_id: str,
    *,
    auth_context: AuthContext | None = None,
    max_depth: int = 3,
    include_types: list[str] | None = None,
    direction: str = "outgoing",
) -> dict[str, Any]:
    """Build a permission-filtered asset graph rooted at *asset_id*."""
    # TODO: delegate to intelligence.asset_graph.build_asset_graph(...)
    return {
        "root_node_id": asset_id,
        "nodes": [],
        "edges": [],
        "max_depth": max_depth,
        "actual_depth": 0,
        "truncated": False,
        "_status": "placeholder",
    }


# ---------------------------------------------------------------------------
# Compliance reports
# ---------------------------------------------------------------------------


def generate_compliance_report(
    tenant_scope: TenantScope,
    *,
    auth_context: AuthContext | None = None,
    format: str = "markdown",
    include_sections: list[str] | None = None,
    time_window: str = "30d",
    report_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an automated compliance evidence report."""
    # TODO: delegate to governance.reports.generate_compliance_report(...)
    return {
        "report_id": "placeholder",
        "generated_at": "",
        "tenant_scope": str(tenant_scope),
        "format": format,
        "sections": {},
        "metadata": {
            "coverage_percent": 0,
            "redaction_applied": True,
            "data_freshness": "",
        },
        "missing_data_warnings": ["Intelligence services are not yet implemented"],
        "_status": "placeholder",
    }


__all__ = [
    "get_admission_score",
    "get_alternatives",
    "get_asset_graph",
    "get_recommendations",
    "generate_compliance_report",
    "search_catalog",
]
