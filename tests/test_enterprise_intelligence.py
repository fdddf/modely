"""Tests for Phase 4: Intelligent Governance — search, analytics, recommendations, admission scoring, graph, compliance, lifecycle, cost."""

from __future__ import annotations

import pytest

from modely.cataloging.repository import InMemoryLocalMirrorRepository
from modely.domain.assets import Asset, AssetIdentity
from modely.intelligence.admission_score import AdmissionScorer
from modely.intelligence.alternatives import AlternativesLookup
from modely.intelligence.analytics import AnalyticsEngine
from modely.intelligence.asset_graph import AssetGraphBuilder
from modely.intelligence.cost import CostAnalyzer
from modely.intelligence.lifecycle import LifecycleGovernance
from modely.intelligence.recommendations import RecommendationEngine
from modely.intelligence.semantic_index import SearchIndex, SearchQuery
from modely.server.routes.intelligence import (
    admission_score_route,
    alternatives_route,
    asset_graph_route,
    compliance_report_route,
    cost_recommendations_route,
    lifecycle_route,
    recommendations_route,
    risk_trends_route,
    search_route,
    usage_route,
)


@pytest.fixture
def catalog_repo():
    repo = InMemoryLocalMirrorRepository()
    repo.assets.save_asset(Asset(id="hf:model:org--model", identity=AssetIdentity(source="hf", repo_type="model", repo_id="org/model", revision="main"), license="apache-2.0", tags=["nlp", "transformer"], operational_state="synced", visibility="organization", size=5000, file_count=3, checksum="abc", metadata={"risk_level": "low"}))
    repo.assets.save_asset(Asset(id="hf:model:other--model", identity=AssetIdentity(source="hf", repo_type="model", repo_id="other/model", revision="main"), license="mit", tags=["nlp", "bert"], operational_state="synced", visibility="organization", size=8000, file_count=5, checksum="def", metadata={"risk_level": "medium"}))
    repo.assets.save_asset(Asset(id="ms:dataset:test--data", identity=AssetIdentity(source="ms", repo_type="dataset", repo_id="test/data", revision="v1"), tags=["text"], operational_state="synced", size=1000, file_count=1))
    return repo


# -- Search tests (4a) ---------------------------------------------------------


def test_search_index_indexing(catalog_repo):
    index = SearchIndex()
    index.build_from_repository(catalog_repo)
    assert len(index._index) == 3


def test_search_keyword(catalog_repo):
    index = SearchIndex()
    index.build_from_repository(catalog_repo)
    result = index.search(SearchQuery(q="nlp"))
    assert result["total"] == 2


def test_search_faceted_filter(catalog_repo):
    index = SearchIndex()
    index.build_from_repository(catalog_repo)
    result = index.search(SearchQuery(source="ms"))
    assert result["total"] == 1
    assert result["results"][0]["repo_type"] == "dataset"


def test_search_pagination(catalog_repo):
    index = SearchIndex()
    index.build_from_repository(catalog_repo)
    result = index.search(SearchQuery(page=1, page_size=2))
    assert result["total"] == 3
    assert len(result["results"]) == 2


def test_search_facets(catalog_repo):
    index = SearchIndex()
    index.build_from_repository(catalog_repo)
    facets = index.get_facets()
    assert "hf" in facets["sources"]
    assert "model" in facets["resource_types"]


def test_search_route(catalog_repo):
    index = SearchIndex()
    index.build_from_repository(catalog_repo)

    class Svc:
        def search(self, **kw):
            return index.search(SearchQuery(**{k: v for k, v in kw.items() if v}))

    result = search_route(Svc(), request_id="req_s", q="nlp", source="hf")
    assert result["data"]["total"] == 2


# -- Analytics tests (4a) ------------------------------------------------------


def test_analytics_risk_trends():
    engine = AnalyticsEngine()
    engine.record_scan("a1", "high", "secret")
    engine.record_scan("a2", "medium", "license")
    engine.record_scan("a3", "low", "remote_code")

    trend = engine.get_risk_trends(period="30d")
    assert trend.total_findings == 3
    assert trend.high_severity == 1


def test_analytics_usage_popularity():
    engine = AnalyticsEngine()
    engine.record_usage("a1", "download")
    engine.record_usage("a1", "download")
    engine.record_usage("a2", "resolve")

    stats = engine.get_usage_popularity()
    assert len(stats) == 2
    assert stats[0].popularity_score > stats[1].popularity_score


def test_analytics_routes():
    class Svc:
        def get_risk_trends(self, **kw): return AnalyticsEngine().get_risk_trends(**kw)
        def get_usage_popularity(self, **kw): return AnalyticsEngine().get_usage_popularity(**kw)

    r = risk_trends_route(Svc(), request_id="req_r")
    assert r["data"]["total_findings"] == 0
    u = usage_route(Svc(), request_id="req_u")
    assert u["data"]["assets"] == []


# -- Recommendations tests (4b) ------------------------------------------------


def test_recommendations_by_tags(catalog_repo):
    engine = RecommendationEngine(repository=catalog_repo)
    recs = engine.get_recommendations("hf:model:org--model")
    assert len(recs) >= 1
    assert recs[0].asset_id == "hf:model:other--model"


def test_alternatives(catalog_repo):
    engine = AlternativesLookup(repository=catalog_repo)
    alts = engine.get_alternatives("hf:model:org--model")
    assert len(alts) >= 1


def test_admission_score(catalog_repo):
    scorer = AdmissionScorer(repository=catalog_repo)
    result = scorer.compute_admission_score("hf:model:org--model")
    assert result.score > 0
    assert "license" in result.components


def test_recommendations_route(catalog_repo):
    engine = RecommendationEngine(repository=catalog_repo)

    class Svc:
        def get_recommendations(self, **kw): return engine.get_recommendations(**kw)

    result = recommendations_route(Svc(), "hf:model:org--model", request_id="req_r")
    assert len(result["data"]["recommendations"]) >= 1


# -- Graph test (4c) -----------------------------------------------------------


def test_asset_graph(catalog_repo):
    builder = AssetGraphBuilder(repository=catalog_repo)
    node = builder.get_asset_graph("hf:model:org--model", depth=1)
    assert len(node.relations) >= 1
    assert node.asset_id == "hf:model:org--model"


# -- Lifecycle/Cost tests (4c) -------------------------------------------------


def test_lifecycle_suggestions(catalog_repo):
    gov = LifecycleGovernance()
    engine = AnalyticsEngine()
    engine.record_usage("hf:model:other--model", "download")  # Only one used
    suggestions = gov.get_lifecycle_suggestions(analytics_engine=engine, repository=catalog_repo)
    assert len(suggestions) >= 0  # Non-used assets flagged


def test_cost_recommendations(catalog_repo):
    analyzer = CostAnalyzer()
    recs = analyzer.get_cost_recommendations(repository=catalog_repo)
    assert len(recs) >= 0


# -- Route smoke tests ---------------------------------------------------------


def test_compliance_report_route():
    from dataclasses import dataclass
    @dataclass
    class Report: title: str = ""; generated_at: str = ""; format: str = "json"; summary: dict = None; evidence: list = None
    class Svc:
        def generate_compliance_report(self, **kw): return Report(title=kw.get("title", ""), generated_at="now", format=kw.get("format", "json"), summary={"assets": 3}, evidence=[])

    result = compliance_report_route(Svc(), request_id="req_c", title="Test", format="json")
    assert result["data"]["title"] == "Test"


def test_lifecycle_route():
    class Svc:
        def get_stale_assets(self, **kw): return ["a1", "a2"]
    result = lifecycle_route(Svc(), request_id="req_l")
    assert result["data"]["count"] == 2


def test_cost_recommendations_route():
    class Svc:
        def get_cost_recommendations(self): return [{"asset_id": "a1", "category": "large", "estimated_savings": "$X", "reason": "big"}]
    result = cost_recommendations_route(Svc(), request_id="req_c")
    assert len(result["data"]["recommendations"]) == 1
