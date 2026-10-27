"""Unit tests for search dedupe helpers."""

from modely.search.dedupe import dedupe_results, format_grouped_json, format_grouped_table, normalize_repo_name
from modely.search.types import SearchResult


def test_normalize_repo_name():
    assert normalize_repo_name("Qwen/Qwen2.5_7B") == "qwen2-5-7b"


def test_dedupe_results_groups_by_normalized_name():
    results = [
        SearchResult("org/Qwen2.5_7B", "hf", "model", downloads=10),
        SearchResult("owner/qwen2.5-7b", "ms", "model", downloads=5),
        SearchResult("other/bert", "hf", "model", downloads=1),
    ]
    groups = dedupe_results(results)
    qwen = next(g for g in groups if g["key"] == "qwen2-5-7b")
    assert qwen["count"] == 2
    assert qwen["sources"] == ["hf", "ms"]
    assert "qwen2-5-7b" in format_grouped_table(groups, compare=True)
    assert "qwen2-5-7b" in format_grouped_json(groups)
