"""Tests for modely cache system."""

import os
import shutil
import tempfile

import pytest

from modely.common.cache import (
    SOURCE_HF,
    SOURCE_MS,
    SOURCE_GITHUB,
    REPO_TYPE_MODEL,
    REPO_TYPE_DATASET,
    REPO_TYPE_TOOL,
    _repo_type_to_dir,
    get_cache_dir,
    get_source_cache_dir,
    get_repo_type_dir,
    get_repo_cache_dir,
    get_file_path,
    is_cached,
    get_cached_repo_path,
    get_shared_cache_dir,
    set_shared_cache_dir,
    list_cache,
    clean_cache,
    cache_info,
    find_duplicate_files,
    _format_size,
)


@pytest.fixture
def tmp_cache(tmp_path):
    """Provide a temporary cache directory, cleaned up after test."""
    cache_dir = str(tmp_path / "modely_cache")
    os.makedirs(cache_dir, exist_ok=True)
    yield cache_dir
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


class TestConstants:
    def test_source_constants(self):
        assert SOURCE_HF == "hf"
        assert SOURCE_MS == "ms"
        assert SOURCE_GITHUB == "github"

    def test_repo_type_constants(self):
        assert REPO_TYPE_MODEL == "models"
        assert REPO_TYPE_DATASET == "datasets"
        assert REPO_TYPE_TOOL == "tools"


class TestRepoTypeMapping:
    def test_model_to_dir(self):
        assert _repo_type_to_dir("model") == "models"

    def test_dataset_to_dir(self):
        assert _repo_type_to_dir("dataset") == "datasets"

    def test_tool_to_dir(self):
        assert _repo_type_to_dir("tool") == "tools"

    def test_unknown_passthrough(self):
        assert _repo_type_to_dir("unknown") == "unknown"


class TestCacheDir:
    def test_explicit_dir(self, tmp_cache):
        result = get_cache_dir(tmp_cache)
        assert result == os.path.abspath(tmp_cache)
        assert os.path.isdir(result)

    def test_env_variable(self, tmp_cache, monkeypatch):
        monkeypatch.setenv("MODELY_CACHE", tmp_cache)
        result = get_cache_dir()
        assert result == os.path.abspath(tmp_cache)

    def test_shared_cache_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("modely.common.cache.CONFIG_FILE", str(config_file))
        shared = tmp_path / "shared"

        set_shared_cache_dir(str(shared))

        assert get_shared_cache_dir() == os.path.abspath(shared)
        assert cache_info()["shared_cache_dir"] == os.path.abspath(shared)


class TestCacheStructure:
    def test_hf_model_path(self, tmp_cache):
        path = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        assert path == os.path.join(tmp_cache, "hf", "models", "gpt2", "main")
        assert os.path.isdir(path)

    def test_ms_dataset_path(self, tmp_cache):
        path = get_repo_cache_dir("owner/data", "dataset", "master", "ms", tmp_cache)
        assert path == os.path.join(tmp_cache, "ms", "datasets", "owner--data", "master")

    def test_github_tool_path(self, tmp_cache):
        path = get_repo_cache_dir("torvalds/linux", "tool", "master", "github", tmp_cache)
        assert path == os.path.join(tmp_cache, "github", "tools", "torvalds--linux", "master")

    def test_github_model_type_still_uses_tools_path(self, tmp_cache):
        path = get_repo_cache_dir("keras-team/keras", "model", "master", "github", tmp_cache)
        assert path == os.path.join(tmp_cache, "github", "tools", "keras-team--keras", "master")
        assert os.path.join("github", "models") not in path

    def test_repo_id_normalization(self, tmp_cache):
        path = get_repo_cache_dir("owner/repo-name", "tool", "main", "github", tmp_cache)
        assert "owner--repo-name" in path

    def test_file_path(self, tmp_cache):
        path = get_file_path("gpt2", "config.json", "main", "model", "hf", tmp_cache)
        assert path == os.path.join(tmp_cache, "hf", "models", "gpt2", "main", "config.json")


class TestIsCached:
    def test_not_cached(self, tmp_cache):
        assert not is_cached("gpt2", "config.json", "main", "model", "hf", tmp_cache)

    def test_cached_file(self, tmp_cache):
        path = get_file_path("gpt2", "config.json", "main", "model", "hf", tmp_cache)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{}")
        assert is_cached("gpt2", "config.json", "main", "model", "hf", tmp_cache)

    def test_empty_file_not_cached(self, tmp_cache):
        path = get_file_path("gpt2", "config.json", "main", "model", "hf", tmp_cache)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            pass
        assert not is_cached("gpt2", "config.json", "main", "model", "hf", tmp_cache)


class TestGetCachedRepoPath:
    def test_not_cached(self, tmp_cache):
        result = get_cached_repo_path("gpt2", "model", "main", "hf", tmp_cache)
        assert result is None

    def test_empty_dir_not_cached(self, tmp_cache):
        get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        result = get_cached_repo_path("gpt2", "model", "main", "hf", tmp_cache)
        # Empty dir returns None
        assert result is None

    def test_cached_repo(self, tmp_cache):
        repo_dir = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        with open(os.path.join(repo_dir, "config.json"), "w") as f:
            f.write("{}")
        result = get_cached_repo_path("gpt2", "model", "main", "hf", tmp_cache)
        assert result == repo_dir


class TestListCache:
    def test_empty_cache(self, tmp_cache):
        assert list_cache(tmp_cache) == []

    def test_list_hf_model(self, tmp_cache):
        repo_dir = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        with open(os.path.join(repo_dir, "config.json"), "w") as f:
            f.write("{}")
        repos = list_cache(tmp_cache)
        assert len(repos) == 1
        assert repos[0]["source"] == "hf"
        assert repos[0]["repo_type"] == "model"
        assert repos[0]["repo_id"] == "gpt2"

    def test_list_github_tool(self, tmp_cache):
        repo_dir = get_repo_cache_dir("torvalds/linux", "tool", "master", "github", tmp_cache)
        with open(os.path.join(repo_dir, "README"), "w") as f:
            f.write("hello")
        repos = list_cache(tmp_cache)
        assert len(repos) == 1
        assert repos[0]["source"] == "github"
        assert repos[0]["repo_type"] == "tool"
        assert repos[0]["repo_id"] == "torvalds/linux"

    def test_list_all_sources(self, tmp_cache):
        # HF model
        hf_dir = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        with open(os.path.join(hf_dir, "config.json"), "w") as f:
            f.write("{}")
        # MS model
        ms_dir = get_repo_cache_dir("owner/model", "model", "master", "ms", tmp_cache)
        with open(os.path.join(ms_dir, "config.json"), "w") as f:
            f.write("{}")
        # GitHub tool
        gh_dir = get_repo_cache_dir("owner/repo", "tool", "main", "github", tmp_cache)
        with open(os.path.join(gh_dir, "README"), "w") as f:
            f.write("hello")

        repos = list_cache(tmp_cache)
        assert len(repos) == 3
        sources = {r["source"] for r in repos}
        assert sources == {"hf", "ms", "github"}

    def test_list_with_detail(self, tmp_cache):
        repo_dir = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        with open(os.path.join(repo_dir, "config.json"), "w") as f:
            f.write("{}")
        with open(os.path.join(repo_dir, "model.bin"), "w") as f:
            f.write("x" * 100)

        repos = list_cache(tmp_cache, detail=True)
        assert len(repos) == 1
        assert "files" in repos[0]
        assert len(repos[0]["files"]) == 2


class TestCleanCache:
    def test_clean_all(self, tmp_cache):
        repo_dir = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        with open(os.path.join(repo_dir, "config.json"), "w") as f:
            f.write("{}")
        cleaned = clean_cache(cache_dir=tmp_cache)
        assert cleaned > 0
        assert not os.path.exists(os.path.join(repo_dir, "config.json"))
        assert os.path.isdir(tmp_cache)

    def test_clean_specific_repo(self, tmp_cache):
        # Create two repos
        dir1 = get_repo_cache_dir("gpt2", "model", "main", "hf", tmp_cache)
        dir2 = get_repo_cache_dir("bert", "model", "main", "hf", tmp_cache)
        with open(os.path.join(dir1, "f1"), "w") as f:
            f.write("x")
        with open(os.path.join(dir2, "f2"), "w") as f:
            f.write("y")

        clean_cache(repo_id="gpt2", cache_dir=tmp_cache)
        # gpt2 cleaned, bert still exists
        assert not os.path.exists(os.path.join(dir1, "f1"))
        assert os.path.exists(os.path.join(dir2, "f2"))

    def test_clean_github_tool(self, tmp_cache):
        repo_dir = get_repo_cache_dir("owner/repo", "tool", "main", "github", tmp_cache)
        with open(os.path.join(repo_dir, "README"), "w") as f:
            f.write("hello")
        clean_cache(repo_id="owner/repo", cache_dir=tmp_cache)
        assert not os.path.exists(os.path.join(repo_dir, "README"))


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(500) == "500.00 B"

    def test_kilobytes(self):
        assert _format_size(1024) == "1.00 KB"

    def test_megabytes(self):
        assert _format_size(1024 * 1024) == "1.00 MB"

    def test_gigabytes(self):
        assert _format_size(1024 ** 3) == "1.00 GB"



def test_find_duplicate_files_reports_reclaimable_size(tmp_cache):
    a = os.path.join(tmp_cache, "a.bin")
    b_dir = os.path.join(tmp_cache, "nested")
    os.makedirs(b_dir, exist_ok=True)
    b = os.path.join(b_dir, "b.bin")
    with open(a, "w") as f:
        f.write("same")
    with open(b, "w") as f:
        f.write("same")

    report = find_duplicate_files(tmp_cache)

    assert len(report["duplicate_groups"]) == 1
    assert report["reclaimable_size"] == 4


class TestCacheInfo:
    def test_cache_info(self, tmp_cache):
        info = cache_info(tmp_cache)
        assert "cache_dir" in info
        assert "total_size" in info
        assert "total_size_str" in info
        assert info["cache_dir"] == os.path.abspath(tmp_cache)
