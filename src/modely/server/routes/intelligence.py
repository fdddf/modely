"""Intelligence route adapters for Phase 4 enterprise API."""

from __future__ import annotations

from ..schemas.envelopes import Pagination, error_response, success_response
from ..schemas.intelligence import (
    AdmissionScoreResponse,
    AssetGraphNode,
    ComplianceReportResponse,
    Recommendation,
    RecommendationsResponse,
    RiskTrendsResponse,
    SearchResponse,
    SearchResultItem,
    UsagePopularityResponse,
)


# -- Search (4a) ---------------------------------------------------------------


def search_route(service, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Execute a faceted search query.

    GET /api/v1/search
    """

    q = query_params.get("q", "").strip()
    result = service.search(
        q=q,
        source=query_params.get("source"),
        resource_type=query_params.get("resource_type"),
        license=query_params.get("license"),
        risk_level=query_params.get("risk_level"),
        approval_status=query_params.get("approval_status"),
        tags=query_params.get("tags", "").split(",") if query_params.get("tags") else None,
        operational_state=query_params.get("operational_state"),
        page=int(query_params.get("page", 1)),
        page_size=int(query_params.get("page_size", 20)),
        sort=query_params.get("sort", ""),
    )

    results = [
        SearchResultItem(
            asset_id=r.get("asset_id", ""), source=r.get("source", ""), repo_type=r.get("repo_type", ""),
            repo_id=r.get("repo_id", ""), revision=r.get("revision"), license=r.get("license"),
            tags=r.get("tags", []), score=r.get("score", 0.0),
        )
        for r in result.get("results", [])
    ]

    pagination = Pagination(total=result.get("total", 0), page=result.get("page", 1), page_size=result.get("page_size", 20))
    response = SearchResponse(results=results, total=result.get("total", 0), page=result.get("page", 1), page_size=result.get("page_size", 20), facets=result.get("facets", {}))
    return success_response({"results": [r.to_dict() for r in results], "total": response.total, "page": response.page, "page_size": response.page_size, "facets": response.facets}, request_id=request_id, pagination=pagination)


# -- Analytics (4a) ------------------------------------------------------------


def risk_trends_route(service, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return risk trend analytics.

    GET /api/v1/analytics/risk
    """

    period = query_params.get("period", "30d")
    trend = service.get_risk_trends(period=period)
    response = RiskTrendsResponse(
        period=trend.period, total_findings=trend.total_findings, high_severity=trend.high_severity,
        medium_severity=trend.medium_severity, low_severity=trend.low_severity, trend_direction=trend.trend_direction,
    )
    return success_response(response.to_dict(), request_id=request_id)


def usage_route(service, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return usage popularity analytics.

    GET /api/v1/analytics/usage
    """

    asset_id = query_params.get("asset_id", "")
    stats = service.get_usage_popularity(asset_id=asset_id)
    response = UsagePopularityResponse(assets=[s.to_dict() for s in stats])
    return success_response(response.to_dict(), request_id=request_id)


# -- Recommendations (4b) ------------------------------------------------------


def recommendations_route(service, asset_id: str, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return recommendations for an asset.

    GET /api/v1/assets/{id}/recommendations
    """

    limit = int(query_params.get("limit", 5))
    recs = service.get_recommendations(asset_id=asset_id, limit=limit)
    items = [Recommendation(asset_id=r.asset_id, reason=r.reason, confidence=r.confidence).to_dict() for r in recs]
    return success_response(RecommendationsResponse(asset_id=asset_id, recommendations=[Recommendation(**i) for i in items]).to_dict(), request_id=request_id)


def alternatives_route(service, asset_id: str, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return approved alternatives for an asset.

    GET /api/v1/assets/{id}/alternatives
    """

    limit = int(query_params.get("limit", 5))
    alts = service.get_alternatives(asset_id=asset_id, limit=limit)
    items = [Recommendation(asset_id=a.asset_id, reason=a.reason, confidence=a.confidence).to_dict() for a in alts]
    return success_response({"asset_id": asset_id, "alternatives": items}, request_id=request_id)


def admission_score_route(service, asset_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    """Return admission score for an asset.

    POST /api/v1/assets/{id}/admission-score
    """

    score = service.compute_admission_score(asset_id=asset_id)
    response = AdmissionScoreResponse(asset_id=asset_id, score=score.score, components=score.components, evidence=score.evidence)
    return success_response(response.to_dict(), request_id=request_id)


# -- Graph (4c) ----------------------------------------------------------------


def asset_graph_route(service, asset_id: str, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return the asset graph for an asset.

    GET /api/v1/graph/assets/{id}
    """

    depth = int(query_params.get("depth", 1))
    node = service.get_asset_graph(asset_id=asset_id, depth=depth)
    response = AssetGraphNode(asset_id=node.asset_id, relations=node.relations, metadata=node.metadata)
    return success_response(response.to_dict(), request_id=request_id)


# -- Compliance (4c) -----------------------------------------------------------


def compliance_report_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Generate a compliance report.

    POST /api/v1/reports/compliance
    """

    title = payload.get("title", "Compliance Report")
    fmt = payload.get("format", "json")
    report = service.generate_compliance_report(title=title, format=fmt)
    response = ComplianceReportResponse(title=report.title, generated_at=report.generated_at, format=report.format, summary=report.summary, evidence=report.evidence)
    return success_response(response.to_dict(), request_id=request_id)


# -- Lifecycle/Cost (4c) -------------------------------------------------------


def lifecycle_route(service, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return lifecycle analytics.

    GET /api/v1/analytics/lifecycle
    """
    stale = service.get_stale_assets(threshold_days=int(query_params.get("threshold_days", 90)))
    return success_response({"stale_assets": stale, "count": len(stale)}, request_id=request_id)


def cost_analytics_route(service, *, request_id: str = "req_unknown", **query_params) -> dict:
    """Return cost analytics overview.

    GET /api/v1/analytics/cost
    """
    recs = service.get_cost_recommendations()
    return success_response({"recommendations": recs, "total": len(recs)}, request_id=request_id)


def cost_recommendations_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """Generate cost optimization recommendations.

    POST /api/v1/analytics/cost/recommendations
    """
    results = service.get_cost_recommendations()
    return success_response({"recommendations": results}, request_id=request_id)


__all__ = [
    "admission_score_route",
    "alternatives_route",
    "asset_graph_route",
    "compliance_report_route",
    "cost_analytics_route",
    "cost_recommendations_route",
    "lifecycle_route",
    "recommendations_route",
    "risk_trends_route",
    "search_route",
    "usage_route",
]
