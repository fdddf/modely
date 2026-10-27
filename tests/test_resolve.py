"""Unit tests for cross-source resolve helpers."""

import json

from modely.resolve import format_resolve_table, resolve_resource, score_candidate
from modely.search.types import SearchResult


def test_resolve_groups_exact_cross_source_matches(monkeypatch):
    results = [
        SearchResult("org/Qwen2.5_7B", "hf", "model", downloads=100, author="org", pipeline_tag="text-generation", license="apache-2.0"),
        SearchResult("owner/qwen2.5-7b", "ms", "model", downloads=50, author="owner", pipeline_tag="text-generation", license="apache-2.0"),
    ]
    monkeypatch.setattr("modely.intelligence.resolve.search", lambda *a, **k: results)

    resolved = resolve_resource("qwen2.5-7b", threshold=0.1)

    assert resolved.canonical == "Qwen2.5_7B"
    assert len(resolved.candidates) == 2
    assert {c.source for c in resolved.candidates} == {"hf", "ms"}
    assert all("name-exact" in c.signals for c in resolved.candidates)
    assert all("cross-source-group" in c.signals for c in resolved.candidates)


def test_resolve_threshold_filters_weak_matches(monkeypatch):
    results = [
        SearchResult("org/Qwen2.5-7B", "hf", "model"),
        SearchResult("org/bert-base", "hf", "model"),
    ]
    monkeypatch.setattr("modely.intelligence.resolve.search", lambda *a, **k: results)

    resolved = resolve_resource("qwen2.5-7b", threshold=0.35)

    assert [c.repo_id for c in resolved.candidates] == ["org/Qwen2.5-7B"]


def test_resolve_json_serialization_contains_candidate_schema(monkeypatch):
    results = [SearchResult("org/model", "hf", "model", downloads=1)]
    monkeypatch.setattr("modely.intelligence.resolve.search", lambda *a, **k: results)

    data = resolve_resource("model", threshold=0.1).to_dict()

    assert data["query"] == "model"
    assert data["canonical"] == "model"
    assert data["groups"][0]["key"] == "model"
    candidate = data["candidates"][0]
    assert candidate["source"] == "hf"
    assert candidate["repo_id"] == "org/model"
    assert candidate["modely_uri"] == "hf://models/org/model"
    assert isinstance(candidate["confidence"], float)
    assert "signals" in candidate
    assert candidate["result"]["id"] == "org/model"


def test_resolve_table_includes_fields(monkeypatch):
    results = [SearchResult("org/model", "hf", "model", downloads=1)]
    monkeypatch.setattr("modely.intelligence.resolve.search", lambda *a, **k: results)

    output = format_resolve_table(resolve_resource("model", threshold=0.1))

    assert "Canonical: model" in output
    assert "org/model" in output
    assert "hf://models/org/model" in output
    assert "name-exact" in output


def test_score_candidate_adds_group_signals():
    result = SearchResult("org/model", "hf", "model", downloads=1, pipeline_tag="nlp", license="mit")
    peer = SearchResult("other/model", "ms", "model", pipeline_tag="nlp", license="mit")
    group = {"sources": ["hf", "ms"], "results": [result, peer]}

    score, signals = score_candidate("model", result, group)

    assert score > 0.7
    assert "cross-source-group" in signals
    assert "task-match" in signals
    assert "license-match" in signals


def test_score_candidate_handles_structured_author_metadata():
    result = SearchResult("org/model", "ms", "model", author={"Name": "org"})
    peer = SearchResult("other/model", "hf", "model", author="other")
    group = {"sources": ["ms", "hf"], "results": [result, peer]}

    score, signals = score_candidate("model", result, group)

    assert score > 0
    assert "cross-source-group" in signals


def test_resolve_uri_query_uses_repo_name(monkeypatch):
    captured = {}

    def fake_search(keyword, **kwargs):
        captured["keyword"] = keyword
        return [SearchResult("Qwen/Qwen2.5-7B-Instruct", "hf", "model")]

    monkeypatch.setattr("modely.intelligence.resolve.search", fake_search)

    resolve_resource("hf://models/Qwen/Qwen2.5-7B-Instruct", threshold=0.1)

    assert captured["keyword"] == "Qwen2.5-7B-Instruct"


def test_resolve_accepts_auto_repo_type(monkeypatch):
    captured = {}
    results = [
        SearchResult("org/model", "hf", "model"),
        SearchResult("org/dataset", "hf", "dataset"),
    ]

    def fake_search(keyword, **kwargs):
        captured.update(kwargs)
        return results

    monkeypatch.setattr("modely.intelligence.resolve.search", fake_search)

    resolved = resolve_resource("org", repo_type="auto", threshold=0.1)

    assert captured["repo_type"] == "auto"
    assert {candidate.repo_type for candidate in resolved.candidates} <= {"model", "dataset"}


def test_resolve_json_output_is_valid(monkeypatch, capsys):
    from modely.resolve import print_resolve_result

    results = [SearchResult("org/model", "hf", "model")]
    monkeypatch.setattr("modely.intelligence.resolve.search", lambda *a, **k: results)

    print_resolve_result(resolve_resource("model", threshold=0.1), as_json=True)
    parsed = json.loads(capsys.readouterr().out)

    assert parsed["candidates"][0]["repo_id"] == "org/model"
