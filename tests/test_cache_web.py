"""Unit tests for the local cache browser."""

import os
import json

from modely.cache_web import build_cache_browser_data, render_cache_index
from modely.common.cache import get_repo_cache_dir


def test_build_cache_browser_data_groups_cached_assets(tmp_path):
    cache_dir = str(tmp_path / "cache")
    repo_dir = get_repo_cache_dir("org/model", "model", "main", "hf", cache_dir)
    with open(os.path.join(repo_dir, "config.json"), "w") as f:
        f.write("{}")
    with open(os.path.join(repo_dir, "model.safetensors"), "w") as f:
        f.write("x" * 100)

    data = build_cache_browser_data(cache_dir)

    assert data["summary"]["total_entries"] == 1
    assert data["filters"]["sources"] == ["hf"]
    assert data["filters"]["repo_types"] == ["model"]
    assert data["insights"]["by_source"][0]["name"] == "hf"
    assert data["insights"]["by_repo_type"][0]["name"] == "model"
    assert data["insights"]["largest_entries"][0]["repo_id"] == "org/model"
    entry = data["entries"][0]
    assert entry["repo_id"] == "org/model"
    assert entry["file_count"] == 2
    assert entry["categories"]["weights"] == 1
    assert entry["categories"]["metadata"] == 1
    assert entry["health"]["status"] == "ok"


def test_render_cache_index_contains_cards_and_filters(tmp_path):
    cache_dir = str(tmp_path / "cache")
    repo_dir = get_repo_cache_dir("org/model", "model", "main", "hf", cache_dir)
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write("# model")

    html = render_cache_index(build_cache_browser_data(cache_dir))

    assert "Local model and dataset cache" in html
    assert "Cache dir" in html
    assert "<code>" in html
    assert "org/model" in html
    assert "hf" in html
    assert "model" in html
    assert "README.md" in html
    assert "/api/catalog" in html
    assert "data-filter-kind='source'" in html
    assert "onclick='toggleFilter(this)'" in html
    assert 'data-source="hf"' in html
    assert 'data-repo-type="model"' in html
    assert 'data-revision="main"' in html
    assert "activeFilters" in html
    assert "Size by source" in html
    assert "Largest entries" in html
    assert "Cleanup plan" in html
    assert "Ready" in html
    assert "badge-source" in html
    assert "badge-type" in html
    assert "category-pill" in html
    assert "category-card" in html


def test_cache_browser_data_is_json_serializable(tmp_path):
    cache_dir = str(tmp_path / "cache")
    repo_dir = get_repo_cache_dir("owner/repo", "tool", "main", "github", cache_dir)
    with open(os.path.join(repo_dir, "README"), "w") as f:
        f.write("hello")

    payload = json.dumps(build_cache_browser_data(cache_dir))

    assert "owner/repo" in payload
