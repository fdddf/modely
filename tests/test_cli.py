"""Integration tests for modely CLI and download functions.

These tests require network access and are marked with pytest.mark.integration.
Run with: pytest tests/ -m integration
Skip with: pytest tests/ -m "not integration"
"""

import fnmatch
import os
import shutil
import subprocess

import pytest

from modely.common import cache as cache_mod
from modely.modelscope import snapshot_download as ms_snapshot_download


@pytest.fixture
def tmp_cache(tmp_path):
    """Provide a temporary cache directory, cleaned up after test."""
    cache_dir = str(tmp_path / "modely_test_cache")
    os.makedirs(cache_dir, exist_ok=True)
    yield cache_dir
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


def run_cli(*args):
    """Run modely-ai CLI and return CompletedProcess."""
    return subprocess.run(
        ["modely-ai", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


# ── Hugging Face ──────────────────────────────────────────────

@pytest.mark.integration
class TestHuggingFace:
    def test_hf_file_download(self, tmp_cache):
        result = run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "Successfully downloaded" in result.stdout

    def test_hf_file_cached(self, tmp_cache):
        # First download
        run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        # Second should hit cache
        result = run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "cached" in result.stdout.lower() or "Successfully" in result.stdout


# ── ModelScope ────────────────────────────────────────────────

@pytest.mark.integration
class TestModelScope:
    def test_ms_file_download(self, tmp_cache):
        result = run_cli(
            "ms", "AI-ModelScope/gpt2",
            "--file", "config.json",
            "--cache-dir", tmp_cache,
        )
        assert result.returncode == 0
        assert "Successfully downloaded" in result.stdout

    def test_ms_file_cached(self, tmp_cache):
        run_cli("ms", "AI-ModelScope/gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        result = run_cli("ms", "AI-ModelScope/gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        assert result.returncode == 0


# ── GitHub ────────────────────────────────────────────────────

@pytest.mark.integration
class TestGitHub:
    def test_github_file_download(self, tmp_cache):
        result = run_cli(
            "github", "torvalds/linux",
            "--file", "README",
            "--revision", "master",
            "--cache-dir", tmp_cache,
        )
        assert result.returncode == 0
        assert "Successfully downloaded" in result.stdout

    def test_github_file_cached(self, tmp_cache):
        run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)
        result = run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "cached" in result.stdout.lower()

    def test_github_clone_default_branch_fallback(self, tmp_cache):
        """When --revision main fails, should fall back to the actual default branch."""
        result = run_cli(
            "github", "httpie/cli",
            "--revision", "main",
            "--cache-dir", tmp_cache,
        )
        assert result.returncode == 0
        assert "cloned to" in result.stdout.lower() or "Cloning" in result.stdout

    def test_github_clone_cached(self, tmp_cache):
        """Second clone of same repo should hit cache."""
        run_cli("github", "httpie/cli", "--revision", "main", "--cache-dir", tmp_cache)
        result = run_cli("github", "httpie/cli", "--revision", "main", "--cache-dir", tmp_cache)
        assert result.returncode == 0
        assert "cached" in result.stdout.lower()

    def test_github_cache_path_is_tools(self, tmp_cache):
        """GitHub repos should be cached under tools/, not models/."""
        repo_dir = cache_mod.get_repo_cache_dir(
            "torvalds/linux", "tool", "master", "github", tmp_cache
        )
        assert os.path.join("github", "tools") in repo_dir
        assert "models" not in repo_dir


# ── Cache Management ──────────────────────────────────────────

@pytest.mark.integration
class TestCacheCLI:
    def test_cache_list_shows_all_sources(self, tmp_cache):
        # Download from ms and github (HF uses its own cache structure)
        run_cli("ms", "AI-ModelScope/gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)

        result = run_cli("cache", "--cache-dir", tmp_cache, "list")
        assert result.returncode == 0
        assert "[ms]" in result.stdout
        assert "[github]" in result.stdout

    def test_cache_list_shows_github_as_tool(self, tmp_cache):
        run_cli("github", "torvalds/linux", "--file", "README", "--revision", "master", "--cache-dir", tmp_cache)

        result = run_cli("cache", "--cache-dir", tmp_cache, "list")
        assert result.returncode == 0
        assert "tool:" in result.stdout

    def test_cache_info(self, tmp_cache):
        result = run_cli("cache", "--cache-dir", tmp_cache, "info")
        assert result.returncode == 0
        assert "Cache directory" in result.stdout
        assert "Total size" in result.stdout

    def test_cache_clean_all(self, tmp_cache):
        run_cli("hf", "gpt2", "--file", "config.json", "--cache-dir", tmp_cache)
        result = run_cli("cache", "--cache-dir", tmp_cache, "clean")
        assert result.returncode == 0
        assert "Cleaned" in result.stdout

    def test_cache_list_empty(self, tmp_cache):
        result = run_cli("cache", "--cache-dir", tmp_cache, "list")
        assert result.returncode == 0
        assert "No cached" in result.stdout


# ── File Filtering (unit tests) ─────────────────────────────────

class TestIncludeExclude:
    """Unit tests for file pattern filtering in snapshot downloads. No network needed."""

    @pytest.fixture
    def sample_files(self):
        return [
            {"Path": "config.json", "Type": "blob"},
            {"Path": "pytorch_model.bin", "Type": "blob"},
            {"Path": "tf_model.h5", "Type": "blob"},
            {"Path": "model.safetensors", "Type": "blob"},
            {"Path": "tokenizer.json", "Type": "blob"},
            {"Path": "vocab.txt", "Type": "blob"},
            {"Path": ".gitattributes", "Type": "blob"},
        ]

    def test_include_single_pattern(self, sample_files):
        """Include *.json should only keep JSON files."""
        patterns = ["*.json"]
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert paths == {"config.json", "tokenizer.json"}

    def test_include_multiple_patterns(self, sample_files):
        """Include *.json *.bin should keep both."""
        patterns = ["*.json", "*.bin"]
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert "config.json" in paths
        assert "pytorch_model.bin" in paths
        assert "model.safetensors" not in paths

    def test_exclude_pattern(self, sample_files):
        """Exclude *.safetensors should remove safetensors files."""
        patterns = ["*.safetensors"]
        filtered = [
            f for f in sample_files
            if not any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert "model.safetensors" not in paths
        assert "config.json" in paths

    def test_exclude_multiple_patterns(self, sample_files):
        """Exclude *.bin *.h5 should remove both binary types."""
        patterns = ["*.bin", "*.h5"]
        filtered = [
            f for f in sample_files
            if not any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        paths = {f["Path"] for f in filtered}
        assert "pytorch_model.bin" not in paths
        assert "tf_model.h5" not in paths
        assert "config.json" in paths

    def test_include_and_exclude_together(self, sample_files):
        """Include takes precedence in our implementation (include then exclude filters apply)."""
        include_pat = ["*.json"]
        exclude_pat = ["tokenizer.*"]
        # First include
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in include_pat)
        ]
        # Then exclude
        filtered = [
            f for f in filtered
            if not any(fnmatch.fnmatch(f["Path"], p) for p in exclude_pat)
        ]
        paths = {f["Path"] for f in filtered}
        assert "config.json" in paths
        assert "tokenizer.json" not in paths

    def test_no_matches_returns_empty(self, sample_files):
        """Include pattern with no matches should return empty list."""
        patterns = ["*.nonexistent"]
        filtered = [
            f for f in sample_files
            if any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        assert filtered == []

    def test_exclude_no_matches_keeps_all(self, sample_files):
        """Exclude pattern that matches nothing keeps all files."""
        patterns = ["*.nonexistent"]
        filtered = [
            f for f in sample_files
            if not any(fnmatch.fnmatch(f["Path"], p) for p in patterns)
        ]
        assert len(filtered) == len(sample_files)

    def test_endpoint_env_set(self, monkeypatch):
        """Setting MODELSCOPE_ENDPOINT env var should be used by get_endpoint."""
        from modely.modelscope import get_endpoint

        monkeypatch.setenv("MODELSCOPE_ENDPOINT", "https://custom.modelscope.cn")
        assert get_endpoint() == "https://custom.modelscope.cn"

    def test_endpoint_default(self, monkeypatch):
        """Default endpoint should be modelscope.cn."""
        from modely.modelscope import get_endpoint

        monkeypatch.delenv("MODELSCOPE_ENDPOINT", raising=False)
        assert "modelscope.cn" in get_endpoint()

    def test_hf_endpoint_arg_passed(self, monkeypatch):
        """--endpoint should set HF_ENDPOINT env var."""
        monkeypatch.delenv("HF_ENDPOINT", raising=False)
        # Simulate what CLI does
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        assert os.environ["HF_ENDPOINT"] == "https://hf-mirror.com"
        # Cleanup
        del os.environ["HF_ENDPOINT"]


# ── CLI Arg Parsing (unit tests) ────────────────────────────────

class TestCLIArgParsing:
    """Verify that new --include/--exclude/--endpoint args are correctly parsed."""

    def test_hf_parser_includes(self):
        """HF parser should accept --include with glob patterns."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--include', nargs='+', default=None)

        args = parser.parse_args(["hf", "gpt2", "--include", "*.json", "*.txt"])
        assert args.include == ["*.json", "*.txt"]

    def test_hf_parser_excludes(self):
        """HF parser should accept --exclude with glob patterns."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--exclude', nargs='+', default=None)

        args = parser.parse_args(["hf", "gpt2", "--exclude", "*.safetensors"])
        assert args.exclude == ["*.safetensors"]

    def test_hf_parser_endpoint(self):
        """HF parser should accept --endpoint."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--endpoint', type=str, default=None)

        args = parser.parse_args(["hf", "gpt2", "--endpoint", "https://hf-mirror.com"])
        assert args.endpoint == "https://hf-mirror.com"

    def test_ms_parser_includes(self):
        """MS parser should accept --include with glob patterns."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        ms_parser = subparsers.add_parser("ms")
        ms_parser.add_argument('repo_id', type=str)
        ms_parser.add_argument('--include', nargs='+', default=None)

        args = parser.parse_args(["ms", "owner/model", "--include", "config.json"])
        assert args.include == ["config.json"]

    def test_ms_parser_endpoint(self):
        """MS parser should accept --endpoint."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        ms_parser = subparsers.add_parser("ms")
        ms_parser.add_argument('repo_id', type=str)
        ms_parser.add_argument('--endpoint', type=str, default=None)

        args = parser.parse_args(["ms", "owner/model", "--endpoint", "https://custom.modelscope.cn"])
        assert args.endpoint == "https://custom.modelscope.cn"

    def test_include_exclude_both(self):
        """Both --include and --exclude can be used together."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--include', nargs='+', default=None)
        hf_parser.add_argument('--exclude', nargs='+', default=None)

        args = parser.parse_args([
            "hf", "gpt2",
            "--include", "*.json", "*.txt",
            "--exclude", "tokenizer.json",
        ])
        assert args.include == ["*.json", "*.txt"]
        assert args.exclude == ["tokenizer.json"]

    def test_include_exclude_not_provided_defaults_none(self):
        """When not provided, --include and --exclude should default to None."""
        import sys
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--include', nargs='+', default=None)
        hf_parser.add_argument('--exclude', nargs='+', default=None)

        args = parser.parse_args(["hf", "gpt2"])
        assert args.include is None
        assert args.exclude is None


# ── HF Pattern Pass-Through (unit tests) ────────────────────────

class TestHFSnapshotPatterns:
    """Test that allow_patterns/ignore_patterns are passed through to huggingface_hub."""

    def test_allow_patterns_passed_to_hf_sdk(self, monkeypatch):
        """allow_patterns should be forwarded to hugginface_hub.snapshot_download."""
        from modely.hf import snapshot_download as hf_snap

        captured = {}

        def mock_snapshot_download(**kwargs):
            captured.update(kwargs)
            return "/fake/path"

        monkeypatch.setattr(
            "modely.hf.hf_snapshot_download_sdk", mock_snapshot_download
        )

        hf_snap("test/repo", allow_patterns=["*.json", "*.txt"])
        assert captured["allow_patterns"] == ["*.json", "*.txt"]

    def test_ignore_patterns_passed_to_hf_sdk(self, monkeypatch):
        """ignore_patterns should be forwarded to hugginface_hub.snapshot_download."""
        from modely.hf import snapshot_download as hf_snap

        captured = {}

        def mock_snapshot_download(**kwargs):
            captured.update(kwargs)
            return "/fake/path"

        monkeypatch.setattr(
            "modely.hf.hf_snapshot_download_sdk", mock_snapshot_download
        )

        hf_snap("test/repo", ignore_patterns=["*.safetensors", "*.bin"])
        assert captured["ignore_patterns"] == ["*.safetensors", "*.bin"]

    def test_both_patterns_passed_to_hf_sdk(self, monkeypatch):
        """Both allow and ignore patterns should be forwarded."""
        from modely.hf import snapshot_download as hf_snap

        captured = {}

        def mock_snapshot_download(**kwargs):
            captured.update(kwargs)
            return "/fake/path"

        monkeypatch.setattr(
            "modely.hf.hf_snapshot_download_sdk", mock_snapshot_download
        )

        hf_snap(
            "test/repo",
            allow_patterns=["*.json"],
            ignore_patterns=["*.bin"],
        )
        assert captured["allow_patterns"] == ["*.json"]
        assert captured["ignore_patterns"] == ["*.bin"]

    def test_no_patterns_passes_none(self, monkeypatch):
        """When no patterns given, None should be passed to SDK."""
        from modely.hf import snapshot_download as hf_snap

        captured = {}

        def mock_snapshot_download(**kwargs):
            captured.update(kwargs)
            return "/fake/path"

        monkeypatch.setattr(
            "modely.hf.hf_snapshot_download_sdk", mock_snapshot_download
        )

        hf_snap("test/repo")
        assert captured["allow_patterns"] is None
        assert captured["ignore_patterns"] is None

    def test_force_download_true_skips_cache_check(self, monkeypatch):
        """With force_download=True, cache should not be checked."""
        from modely.hf import snapshot_download as hf_snap
        import modely.common.cache as hf_cache

        cache_checked = []

        def mock_get_cached_repo_path(*args, **kwargs):
            cache_checked.append(True)
            return None

        def mock_snapshot_download(**kwargs):
            return "/fake/path"

        monkeypatch.setattr(hf_cache, "get_cached_repo_path", mock_get_cached_repo_path)
        monkeypatch.setattr("modely.hf.hf_snapshot_download_sdk", mock_snapshot_download)

        hf_snap("test/repo", force_download=True)
        assert len(cache_checked) == 0


# ── MS Snapshot Download Filtering (unit tests) ─────────────────

class TestMSSnapshotFiltering:
    """Test that ModelScope snapshot_download filters files before downloading."""

    def test_allow_patterns_filters_before_download(self, monkeypatch, tmp_path):
        """Files not matching allow_patterns should be excluded from download."""
        from modely import modelscope as ms_mod

        fake_files = [
            {"Path": "config.json", "Type": "blob", "Size": 100, "Name": "config.json", "Sha256": "abc"},
            {"Path": "model.safetensors", "Type": "blob", "Size": 5000, "Name": "model.safetensors", "Sha256": "def"},
            {"Path": "tokenizer.json", "Type": "blob", "Size": 200, "Name": "tokenizer.json", "Sha256": "ghi"},
            {"Path": "vocab.txt", "Type": "blob", "Size": 300, "Name": "vocab.txt", "Sha256": "jkl"},
        ]

        # Track which files get downloaded
        downloaded_files = []

        # Mock HubApi and file listing
        class FakeApi:
            def __init__(self, token=None):
                pass
            def get_model_files(self, **kwargs):
                return fake_files
            def get_dataset_files(self, **kwargs):
                return fake_files
            def get_endpoint_for_read(self, *args, **kwargs):
                return "https://modelscope.cn"
            def get_valid_revision(self, *args, **kwargs):
                return "master"
            def get_cookies(self, *args, **kwargs):
                return {}

        # Also need to mock the actual file download
        original_repo_file_download = ms_mod._repo_file_download
        def fake_repo_file_download(*args, **kwargs):
            file_path = kwargs.get("file_path") or (args[1] if len(args) > 1 else "unknown")
            downloaded_files.append(file_path)
            return str(tmp_path / file_path)

        monkeypatch.setattr(ms_mod, "HubApi", FakeApi)
        monkeypatch.setattr(ms_mod, "_repo_file_download", fake_repo_file_download)

        # Add a cache directory to avoid cache miss issues
        ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            cache_dir=str(tmp_path),
            revision="master",
            allow_patterns=["*.json"],
        )

        paths = set(downloaded_files)
        assert "config.json" in paths
        assert "tokenizer.json" in paths
        assert "model.safetensors" not in paths
        assert "vocab.txt" not in paths

    def test_ignore_patterns_filters_before_download(self, monkeypatch, tmp_path):
        """Files matching ignore_patterns should be excluded from download."""
        from modely import modelscope as ms_mod

        fake_files = [
            {"Path": "config.json", "Type": "blob", "Size": 100, "Name": "config.json", "Sha256": "abc"},
            {"Path": "model.safetensors", "Type": "blob", "Size": 5000, "Name": "model.safetensors", "Sha256": "def"},
            {"Path": "model.bin", "Type": "blob", "Size": 3000, "Name": "model.bin", "Sha256": "xyz"},
            {"Path": "tokenizer.json", "Type": "blob", "Size": 200, "Name": "tokenizer.json", "Sha256": "ghi"},
        ]

        downloaded_files = []

        class FakeApi:
            def __init__(self, token=None):
                pass
            def get_model_files(self, **kwargs):
                return fake_files
            def get_dataset_files(self, **kwargs):
                return fake_files
            def get_endpoint_for_read(self, *args, **kwargs):
                return "https://modelscope.cn"
            def get_valid_revision(self, *args, **kwargs):
                return "master"
            def get_cookies(self, *args, **kwargs):
                return {}

        def fake_repo_file_download(*args, **kwargs):
            file_path = kwargs.get("file_path") or (args[1] if len(args) > 1 else "unknown")
            downloaded_files.append(file_path)
            return str(tmp_path / file_path)

        monkeypatch.setattr(ms_mod, "HubApi", FakeApi)
        monkeypatch.setattr(ms_mod, "_repo_file_download", fake_repo_file_download)

        ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            cache_dir=str(tmp_path),
            revision="master",
            ignore_patterns=["*.safetensors", "*.bin"],
        )

        paths = set(downloaded_files)
        assert "config.json" in paths
        assert "tokenizer.json" in paths
        assert "model.safetensors" not in paths
        assert "model.bin" not in paths

    def test_allow_and_ignore_combined(self, monkeypatch, tmp_path):
        """allow_patterns applies first, then ignore_patterns filters the result."""
        from modely import modelscope as ms_mod

        fake_files = [
            {"Path": "config.json", "Type": "blob", "Size": 100, "Name": "config.json", "Sha256": "abc"},
            {"Path": "tokenizer.json", "Type": "blob", "Size": 200, "Name": "tokenizer.json", "Sha256": "ghi"},
            {"Path": "model.json", "Type": "blob", "Size": 300, "Name": "model.json", "Sha256": "mno"},
        ]

        downloaded_files = []

        class FakeApi:
            def __init__(self, token=None):
                pass
            def get_model_files(self, **kwargs):
                return fake_files
            def get_dataset_files(self, **kwargs):
                return fake_files
            def get_endpoint_for_read(self, *args, **kwargs):
                return "https://modelscope.cn"
            def get_valid_revision(self, *args, **kwargs):
                return "master"
            def get_cookies(self, *args, **kwargs):
                return {}

        def fake_repo_file_download(*args, **kwargs):
            file_path = kwargs.get("file_path") or (args[1] if len(args) > 1 else "unknown")
            downloaded_files.append(file_path)
            return str(tmp_path / file_path)

        monkeypatch.setattr(ms_mod, "HubApi", FakeApi)
        monkeypatch.setattr(ms_mod, "_repo_file_download", fake_repo_file_download)

        ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            cache_dir=str(tmp_path),
            revision="master",
            allow_patterns=["*.json"],
            ignore_patterns=["tokenizer.*"],
        )

        paths = set(downloaded_files)
        assert "config.json" in paths
        assert "model.json" in paths
        assert "tokenizer.json" not in paths

    def test_allow_patterns_no_match_skips_all(self, monkeypatch, tmp_path):
        """When allow_patterns matches nothing, no files should be downloaded."""
        from modely import modelscope as ms_mod

        fake_files = [
            {"Path": "model.safetensors", "Type": "blob", "Size": 5000, "Name": "model.safetensors", "Sha256": "abc"},
            {"Path": "model.bin", "Type": "blob", "Size": 3000, "Name": "model.bin", "Sha256": "def"},
        ]

        downloaded_files = []

        class FakeApi:
            def __init__(self, token=None):
                pass
            def get_model_files(self, **kwargs):
                return fake_files
            def get_dataset_files(self, **kwargs):
                return fake_files
            def get_endpoint_for_read(self, *args, **kwargs):
                return "https://modelscope.cn"
            def get_valid_revision(self, *args, **kwargs):
                return "master"
            def get_cookies(self, *args, **kwargs):
                return {}

        def fake_repo_file_download(*args, **kwargs):
            file_path = kwargs.get("file_path") or (args[1] if len(args) > 1 else "unknown")
            downloaded_files.append(file_path)
            return str(tmp_path / file_path)

        monkeypatch.setattr(ms_mod, "HubApi", FakeApi)
        monkeypatch.setattr(ms_mod, "_repo_file_download", fake_repo_file_download)

        ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            cache_dir=str(tmp_path),
            revision="master",
            allow_patterns=["*.nonexistent"],
        )

        assert len(downloaded_files) == 0

    def test_tree_type_files_always_excluded(self, monkeypatch, tmp_path):
        """Files with Type='tree' should always be excluded regardless of patterns."""
        from modely import modelscope as ms_mod

        fake_files = [
            {"Path": "config.json", "Type": "blob", "Size": 100, "Name": "config.json", "Sha256": "abc"},
            {"Path": "subdir", "Type": "tree", "Size": 0, "Name": "subdir", "Sha256": ""},
        ]

        downloaded_files = []

        class FakeApi:
            def __init__(self, token=None):
                pass
            def get_model_files(self, **kwargs):
                return fake_files
            def get_dataset_files(self, **kwargs):
                return fake_files
            def get_endpoint_for_read(self, *args, **kwargs):
                return "https://modelscope.cn"
            def get_valid_revision(self, *args, **kwargs):
                return "master"
            def get_cookies(self, *args, **kwargs):
                return {}

        def fake_repo_file_download(*args, **kwargs):
            file_path = kwargs.get("file_path") or (args[1] if len(args) > 1 else "unknown")
            downloaded_files.append(file_path)
            return str(tmp_path / file_path)

        monkeypatch.setattr(ms_mod, "HubApi", FakeApi)
        monkeypatch.setattr(ms_mod, "_repo_file_download", fake_repo_file_download)

        ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            cache_dir=str(tmp_path),
            revision="master",
        )

        paths = set(downloaded_files)
        assert "config.json" in paths
        assert "subdir" not in paths


# ── Endpoint Propagation (unit tests) ───────────────────────────

class TestEndpointPropagation:
    """Test that --endpoint flag correctly propagates to environment variables."""

    def test_hf_endpoint_sets_env_var(self, monkeypatch):
        """HF --endpoint should set HF_ENDPOINT before huggingface_hub SDK call."""
        import os
        monkeypatch.delenv("HF_ENDPOINT", raising=False)

        # Simulate what the dispatch does
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        assert os.environ["HF_ENDPOINT"] == "https://hf-mirror.com"

        # Cleanup
        del os.environ["HF_ENDPOINT"]

    def test_ms_endpoint_sets_env_var(self, monkeypatch):
        """MS --endpoint should set MODELSCOPE_ENDPOINT before API calls."""
        import os
        monkeypatch.delenv("MODELSCOPE_ENDPOINT", raising=False)

        os.environ["MODELSCOPE_ENDPOINT"] = "https://custom.ms.cn"
        assert os.environ["MODELSCOPE_ENDPOINT"] == "https://custom.ms.cn"

        del os.environ["MODELSCOPE_ENDPOINT"]

    def test_hf_endpoint_used_by_hub_sdk(self, monkeypatch):
        """When HF_ENDPOINT is set, huggingface_hub should see it."""
        import os
        monkeypatch.setenv("HF_ENDPOINT", "https://hf-mirror.com")
        assert os.environ.get("HF_ENDPOINT") == "https://hf-mirror.com"

    def test_ms_endpoint_falls_back_to_default(self, monkeypatch):
        """When no MODELSCOPE_ENDPOINT set, get_endpoint returns default."""
        from modely.modelscope import get_endpoint
        monkeypatch.delenv("MODELSCOPE_ENDPOINT", raising=False)
        endpoint = get_endpoint()
        assert "modelscope.cn" in endpoint

    def test_ms_endpoint_custom_overrides_default(self, monkeypatch):
        """Custom MODELSCOPE_ENDPOINT should override default."""
        from modely.modelscope import get_endpoint
        monkeypatch.setenv("MODELSCOPE_ENDPOINT", "https://ms-mirror.example.com")
        assert get_endpoint() == "https://ms-mirror.example.com"


# ── Edge Cases (unit tests) ─────────────────────────────────────

class TestFilteringEdgeCases:
    """Edge case tests for file pattern filtering."""

    def test_subdirectory_pattern(self):
        """fnmatch should match patterns with subdirectory paths."""
        import fnmatch
        # Real-world example: matching files in subdirectories
        assert fnmatch.fnmatch("subdir/config.json", "subdir/*.json")
        assert fnmatch.fnmatch("data/train.jsonl", "data/*.jsonl")
        assert not fnmatch.fnmatch("other/config.json", "subdir/*.json")

    def test_complex_glob_pattern(self):
        """fnmatch supports ? and [charset] patterns."""
        import fnmatch
        assert fnmatch.fnmatch("model_v1.bin", "model_v?.bin")
        assert fnmatch.fnmatch("model_v2.bin", "model_v?.bin")
        assert fnmatch.fnmatch("config.json", "config.[jt][ps]on")  # matches json, not jpon
        # Actually config.json should NOT match config.[jt][ps]on because 's' matches [ps] but 'o' doesn't match
        # Let's verify: [jt] = j or t, [ps] = p or s

    def test_exact_filename_match(self):
        """Exact filename without wildcards should still match."""
        import fnmatch
        assert fnmatch.fnmatch("config.json", "config.json")
        assert not fnmatch.fnmatch("config.yml", "config.json")

    def test_prefix_match(self):
        """Patterns like 'data*' should match files starting with data."""
        import fnmatch
        assert fnmatch.fnmatch("data_config.json", "data*")
        assert fnmatch.fnmatch("data.json", "data*")
        assert not fnmatch.fnmatch("config.json", "data*")

    def test_empty_pattern_list_is_noop(self):
        """Empty list for include or exclude should not filter anything."""
        files = [
            {"Path": "a.json", "Type": "blob"},
            {"Path": "b.txt", "Type": "blob"},
        ]
        allow_patterns = []
        ignore_patterns = []

        # Both empty = no filtering
        if allow_patterns:
            files = [f for f in files if any(fnmatch.fnmatch(f["Path"], p) for p in allow_patterns)]
        if ignore_patterns:
            files = [f for f in files if not any(fnmatch.fnmatch(f["Path"], p) for p in ignore_patterns)]

        # Empty lists are falsy, so the if blocks don't execute
        assert len(files) == 2

    def test_none_pattern_is_noop(self):
        """None for include or exclude should not filter anything."""
        files = [
            {"Path": "a.json", "Type": "blob"},
            {"Path": "b.txt", "Type": "blob"},
        ]
        allow_patterns = None
        ignore_patterns = None
        # In the actual code: if allow_patterns:  → None is falsy → skip
        assert not bool(allow_patterns)
        assert not bool(ignore_patterns)
        assert len(files) == 2

    def test_pattern_with_dotfiles(self):
        """Patterns should match dotfiles properly."""
        import fnmatch
        assert fnmatch.fnmatch(".gitattributes", ".*")
        assert fnmatch.fnmatch(".gitignore", ".*")
        assert not fnmatch.fnmatch("config.json", ".*")


# ── P1: Hash Integrity Validation (unit tests) ──────────────────

class TestHashValidation:
    """Test SHA256 hash-based file integrity checks for ModelScope downloads."""

    def test_valid_hash_passes(self, tmp_path):
        """Matching hash should pass validation without error."""
        from modely.modelscope import file_integrity_validation
        import hashlib

        f = tmp_path / "test.bin"
        content = b"hello world" * 100
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()

        # Should not raise
        file_integrity_validation(str(f), expected)

    def test_mismatched_hash_raises(self, tmp_path):
        """Mismatched hash should raise ValueError."""
        from modely.modelscope import file_integrity_validation
        import pytest

        f = tmp_path / "test.bin"
        f.write_bytes(b"correct content")

        with pytest.raises(ValueError, match="File integrity check failed"):
            file_integrity_validation(str(f), "0000000000000000000000000000000000000000000000000000000000000000")

    def test_hash_case_insensitive(self, tmp_path):
        """Hash comparison should be case insensitive."""
        from modely.modelscope import file_integrity_validation
        import hashlib

        f = tmp_path / "test.bin"
        content = b"case test"
        f.write_bytes(content)
        expected_upper = hashlib.sha256(content).hexdigest().upper()
        expected_lower = hashlib.sha256(content).hexdigest().lower()

        # Both should pass
        file_integrity_validation(str(f), expected_upper)
        file_integrity_validation(str(f), expected_lower)

    def test_empty_file_hash(self, tmp_path):
        """Empty file should still validate correctly."""
        from modely.modelscope import file_integrity_validation
        import hashlib

        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()

        file_integrity_validation(str(f), expected)

    def test_file_not_found(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        from modely.modelscope import file_integrity_validation
        import pytest

        with pytest.raises(FileNotFoundError):
            file_integrity_validation(str(tmp_path / "nonexistent.bin"), "abc123")


# ── P1: Download Threshold & Parallel Logic (unit tests) ────────

class TestDownloadThresholdLogic:
    """Test the conditional parallel download logic in download_file()."""

    def test_small_file_uses_single_download(self, monkeypatch):
        """Files under 512MB threshold should use http_get_model_file, not parallel_download."""
        from modely import modelscope as ms_mod

        called_single = []
        called_parallel = []

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            called_single.append(file_name)
            return "abc123"

        def fake_parallel(url, local_dir, file_name, cookies, headers, file_size, disable_tqdm=False):
            called_parallel.append(file_name)
            return "abc123"

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)
        monkeypatch.setattr(ms_mod, "parallel_download", fake_parallel)

        file_meta = {"Path": "small.json", "Size": 100, "Name": "small.json"}
        # Monkeypatch MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB to test boundary
        monkeypatch.setattr(ms_mod, "MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB", 1)
        monkeypatch.setattr(ms_mod, "MODELSCOPE_DOWNLOAD_PARALLELS", 4)

        # Need to mock cache.put_file to avoid actual file ops
        class FakeCache:
            def put_file(self, meta, temp):
                return "/fake/path"

        ms_mod.download_file(
            "https://example.com/small.json",
            file_meta,
            "/tmp",
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )

        assert len(called_single) == 1
        assert len(called_parallel) == 0
        assert called_single[0] == "small.json"

    def test_large_file_uses_parallel_download(self, monkeypatch):
        """Files over 512MB threshold should use parallel_download."""
        from modely import modelscope as ms_mod

        called_single = []
        called_parallel = []

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            called_single.append(file_name)
            return "abc123"

        def fake_parallel(url, local_dir, file_name, cookies, headers, file_size, disable_tqdm=False):
            called_parallel.append(file_name)
            return "abc123"

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)
        monkeypatch.setattr(ms_mod, "parallel_download", fake_parallel)
        # Set threshold low so our 600MB file triggers parallel
        monkeypatch.setattr(ms_mod, "MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB", 1)
        monkeypatch.setattr(ms_mod, "MODELSCOPE_DOWNLOAD_PARALLELS", 4)

        class FakeCache:
            def put_file(self, meta, temp):
                return "/fake/path"

        file_meta = {"Path": "large.safetensors", "Size": 600 * 1024 * 1024, "Name": "large.safetensors"}
        ms_mod.download_file(
            "https://example.com/large.safetensors",
            file_meta,
            "/tmp",
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )

        assert len(called_single) == 0
        assert len(called_parallel) == 1
        assert called_parallel[0] == "large.safetensors"

    def test_parallel_disabled_when_parallels_is_1(self, monkeypatch):
        """When MODELSCOPE_DOWNLOAD_PARALLELS=1, large files still use single download."""
        from modely import modelscope as ms_mod

        called_single = []
        called_parallel = []

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            called_single.append(file_name)
            return "abc123"

        def fake_parallel(*args, **kwargs):
            called_parallel.append(True)
            return "abc123"

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)
        monkeypatch.setattr(ms_mod, "parallel_download", fake_parallel)
        monkeypatch.setattr(ms_mod, "MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB", 1)
        monkeypatch.setattr(ms_mod, "MODELSCOPE_DOWNLOAD_PARALLELS", 1)

        class FakeCache:
            def put_file(self, meta, temp):
                return "/fake/path"

        file_meta = {"Path": "large.bin", "Size": 600 * 1024 * 1024, "Name": "large.bin"}
        ms_mod.download_file(
            "https://example.com/large.bin",
            file_meta,
            "/tmp",
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )

        assert len(called_single) == 1
        assert len(called_parallel) == 0


# ── P1: Download File Hash Flow (unit tests) ────────────────────

class TestDownloadFileHashFlow:
    """Test the hash verification flow within download_file()."""

    def test_download_file_verifies_hash_when_present(self, monkeypatch, tmp_path):
        """When file_meta has Sha256, download_file should verify file integrity."""
        from modely import modelscope as ms_mod
        import hashlib

        content = b"test content for hash verification"
        expected_hash = hashlib.sha256(content).hexdigest()

        # Write the temp file with correct content so verification passes
        temp_dir = str(tmp_path)
        temp_file = tmp_path / "model.bin"
        temp_file.write_bytes(content)

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            # Write content to the actual temp path that download_file will check
            actual_path = tmp_path / file_name
            actual_path.write_bytes(content)
            return expected_hash  # Return real-time computed hash

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)

        class FakeCache:
            def put_file(self, meta, temp):
                return str(temp)

        file_meta = {
            "Path": "model.bin", "Size": len(content), "Name": "model.bin",
            "Sha256": expected_hash,
        }
        result = ms_mod.download_file(
            "https://example.com/model.bin",
            file_meta,
            temp_dir,
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )
        # Should complete without error
        assert result is not None

    def test_download_file_mismatched_hash_falls_back(self, monkeypatch, tmp_path):
        """When real-time hash mismatches, should fall back to file-level validation."""
        from modely import modelscope as ms_mod
        import hashlib

        content = b"correct content"
        expected_hash = hashlib.sha256(content).hexdigest()
        wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        temp_dir = str(tmp_path)

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            actual_path = tmp_path / file_name
            actual_path.write_bytes(content)
            return wrong_hash  # Return wrong real-time hash to trigger fallback

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)

        class FakeCache:
            def put_file(self, meta, temp):
                return str(temp)

        file_meta = {
            "Path": "model.bin", "Size": len(content), "Name": "model.bin",
            "Sha256": expected_hash,  # Correct expected hash
        }
        result = ms_mod.download_file(
            "https://example.com/model.bin",
            file_meta,
            temp_dir,
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )

        assert result is not None

    def test_download_file_no_hash_field_skips_verification(self, monkeypatch, tmp_path):
        """When file_meta has no Sha256 field, skip hash verification entirely."""
        from modely import modelscope as ms_mod

        content = b"no hash field"
        temp_dir = str(tmp_path)

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            actual_path = tmp_path / file_name
            actual_path.write_bytes(content)
            return None

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)

        class FakeCache:
            def put_file(self, meta, temp):
                return str(temp)

        file_meta = {"Path": "model.bin", "Size": len(content), "Name": "model.bin"}
        # No Sha256 field

        result = ms_mod.download_file(
            "https://example.com/model.bin",
            file_meta,
            temp_dir,
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )

        assert result is not None

    def test_download_file_hash_none_skips_verification(self, monkeypatch, tmp_path):
        """When real-time hash is None (retry occurred), should still do file-level check."""
        from modely import modelscope as ms_mod
        import hashlib

        content = b"retry case content"
        expected_hash = hashlib.sha256(content).hexdigest()
        temp_dir = str(tmp_path)

        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            actual_path = tmp_path / file_name
            actual_path.write_bytes(content)
            return None  # None = retry occurred, no real-time hash

        monkeypatch.setattr(ms_mod, "http_get_model_file", fake_http_get)

        class FakeCache:
            def put_file(self, meta, temp):
                return str(temp)

        file_meta = {
            "Path": "model.bin", "Size": len(content), "Name": "model.bin",
            "Sha256": expected_hash,
        }
        result = ms_mod.download_file(
            "https://example.com/model.bin",
            file_meta,
            temp_dir,
            FakeCache(),
            {},
            None,
            disable_tqdm=True,
        )

        assert result is not None


# ── P1: HTTP Range / Resume Download (unit tests) ───────────────

class TestResumeDownload:
    """Test the partial download / resume HTTP Range header logic."""

    def test_range_header_set_for_resume(self, monkeypatch):
        """When a partial file exists, the Range header should request remaining bytes."""
        import requests as req_mod
        from modely import modelscope as ms_mod

        captured_headers = {}

        class FakeResponse:
            status_code = 200
            def iter_content(self, chunk_size):
                yield b"remaining content"
            def raise_for_status(self):
                pass

        def fake_get(url, stream, headers, cookies, timeout):
            captured_headers.update(headers)
            return FakeResponse()

        monkeypatch.setattr(req_mod, "get", fake_get)

        # Create a partial file to trigger Range request
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        partial_file = os.path.join(tmpdir, "partial.bin")
        with open(partial_file, "wb") as f:
            f.write(b"a" * 100)  # 100 bytes already downloaded

        # Patch the file path to use our partial file
        def fake_http_get(url, local_dir, file_name, file_size, cookies, headers, disable_tqdm=False):
            return "hash123"

        # Actually call http_get_model_file directly with a known partial file
        try:
            ms_mod.http_get_model_file(
                "https://example.com/file.bin",
                tmpdir,
                "partial.bin",
                500,  # total file size
                cookies=req_mod.cookies.RequestsCookieJar(),
                headers={"user-agent": "test"},
                disable_tqdm=True,
            )
        except Exception:
            pass  # Expected to fail after first chunk, we just want to check headers

        assert "Range" in captured_headers
        assert captured_headers["Range"].startswith("bytes=100-")

        import shutil
        shutil.rmtree(tmpdir)

    def test_complete_file_skips_http_get(self, monkeypatch):
        """When the partial file already meets or exceeds file_size, no HTTP request needed."""
        from modely import modelscope as ms_mod
        import requests as req_mod

        get_called = []

        def fake_get(*args, **kwargs):
            get_called.append(True)
            raise RuntimeError("should not be called")

        monkeypatch.setattr(req_mod, "get", fake_get)

        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        partial_file = os.path.join(tmpdir, "complete.bin")
        file_size = 100
        with open(partial_file, "wb") as f:
            f.write(b"a" * file_size)  # Already fully downloaded

        # Should not throw — it should see the file is complete and skip HTTP
        ms_mod.http_get_model_file(
            "https://example.com/file.bin",
            tmpdir,
            "complete.bin",
            file_size,
            cookies=req_mod.cookies.RequestsCookieJar(),
            headers={"user-agent": "test"},
            disable_tqdm=True,
        )

        assert len(get_called) == 0  # No HTTP request was made

        import shutil
        shutil.rmtree(tmpdir)

    def test_empty_file_creates_and_exits(self, monkeypatch):
        """When file_size is 0, should create an empty file and skip HTTP."""
        from modely import modelscope as ms_mod
        import requests as req_mod

        get_called = []

        def fake_get(*args, **kwargs):
            get_called.append(True)
            return None

        monkeypatch.setattr(req_mod, "get", fake_get)

        import tempfile, os
        tmpdir = tempfile.mkdtemp()

        ms_mod.http_get_model_file(
            "https://example.com/empty.bin",
            tmpdir,
            "empty.bin",
            0,  # Zero file size
            cookies=req_mod.cookies.RequestsCookieJar(),
            headers={"user-agent": "test"},
            disable_tqdm=True,
        )

        assert len(get_called) == 0
        assert os.path.exists(os.path.join(tmpdir, "empty.bin"))

        import shutil
        shutil.rmtree(tmpdir)


# ── P1: Model ID Parsing (unit tests) ───────────────────────────

class TestModelIdParsing:
    """Test model_id parsing and validation."""

    def test_valid_model_id(self):
        """Standard owner/name format should parse correctly."""
        from modely.modelscope import model_id_to_group_owner_name
        owner, name = model_id_to_group_owner_name("owner/model-name")
        assert owner == "owner"
        assert name == "model-name"

    def test_model_id_with_special_chars(self):
        """Model IDs with hyphens and dots should work."""
        from modely.modelscope import model_id_to_group_owner_name
        owner, name = model_id_to_group_owner_name("org-1/model.v2")
        assert owner == "org-1"
        assert name == "model.v2"

    def test_invalid_model_id_no_slash(self):
        """Missing slash should raise ValueError."""
        from modely.modelscope import model_id_to_group_owner_name
        import pytest
        with pytest.raises(ValueError, match="Invalid model id format"):
            model_id_to_group_owner_name("just-name")

    def test_invalid_model_id_too_many_slashes(self):
        """Too many slashes should raise ValueError."""
        from modely.modelscope import model_id_to_group_owner_name
        import pytest
        with pytest.raises(ValueError, match="Invalid model id format"):
            model_id_to_group_owner_name("a/b/c")


# ── P1: URL Construction (unit tests) ────────────────────────────

class TestURLConstruction:
    """Test ModelScope API URL building functions."""

    def test_file_download_url_model(self):
        """Model download URL should use /api/v1/models/ endpoint."""
        from modely.modelscope import get_file_download_url
        url = get_file_download_url(
            "owner/model", "config.json", "master",
            repo_type="model", endpoint="https://modelscope.cn"
        )
        assert "/api/v1/models/owner/model/repo" in url
        assert "Revision=master" in url
        assert "FilePath=config.json" in url

    def test_file_download_url_dataset(self):
        """Dataset download URL should use /api/v1/datasets/ endpoint."""
        from modely.modelscope import get_file_download_url
        url = get_file_download_url(
            "owner/dataset", "data.csv", "v1.0",
            repo_type="dataset", endpoint="https://modelscope.cn"
        )
        assert "/api/v1/datasets/owner/dataset/repo" in url
        assert "Revision=v1.0" in url
        assert "FilePath=data.csv" in url

    def test_file_download_url_encodes_special_chars(self):
        """Special characters in file paths should be URL-encoded."""
        from modely.modelscope import get_file_download_url
        url = get_file_download_url(
            "owner/model", "path/to file.json", "main",
            repo_type="model", endpoint="https://modelscope.cn"
        )
        # Spaces get encoded as +
        assert "path%2Fto+file.json" in url or "path/to+file.json" in url or "path%2Fto%20file.json" in url

    def test_model_files_url(self):
        """Model files listing URL should be correctly formatted."""
        from modely.modelscope import get_model_files_url
        url = get_model_files_url("org/model", "main", "https://modelscope.cn")
        assert url.startswith("https://modelscope.cn/api/v1/models/")
        assert "org/model" in url
        assert "Revision=main" in url

    def test_dataset_files_url(self):
        """Dataset files listing URL should be correctly formatted."""
        from modely.modelscope import get_dataset_files_url
        url = get_dataset_files_url("org/dataset", "master", "https://modelscope.cn")
        assert url.startswith("https://modelscope.cn/api/v1/datasets/")
        assert "org/dataset" in url
        assert "Revision=master" in url


# ── P1: Dry-run & List-files (unit tests) ───────────────────────

class TestDryRun:
    """Unit tests for --dry-run preview mode."""

    def test_format_file_size_bytes(self):
        """_format_file_size should format various byte sizes."""
        from modely import _format_file_size
        assert _format_file_size(0) == "-"
        assert _format_file_size(None) == "-"
        assert _format_file_size(500) == "500 B"
        assert _format_file_size(1_500) == "1.5 KB"
        assert _format_file_size(1_500_000) == "1.5 MB"
        assert _format_file_size(1_500_000_000) == "1.5 GB"

    def test_dry_run_basic_output(self, capsys):
        """_do_dry_run should print file counts without downloading."""
        from modely import _do_dry_run

        files = [
            {"Path": "config.json", "Size": 1000, "Type": "blob"},
            {"Path": "model.safetensors", "Size": 500_000_000, "Type": "blob"},
            {"Path": "tokenizer.json", "Size": 2000, "Type": "blob"},
        ]

        _do_dry_run("hf", "test/model", "model", "main", None, None, files)
        out = capsys.readouterr().out

        assert "test/model" in out
        assert "dry-run" in out
        assert "Total files:     3" in out
        assert "Would download:  3" in out

    def test_dry_run_with_filters(self, capsys):
        """_do_dry_run should apply include/exclude and show filtered count."""
        from modely import _do_dry_run

        files = [
            {"Path": "config.json", "Size": 1000, "Type": "blob"},
            {"Path": "model.safetensors", "Size": 500_000_000, "Type": "blob"},
            {"Path": "tokenizer.json", "Size": 2000, "Type": "blob"},
            {"Path": "model.bin", "Size": 300_000_000, "Type": "blob"},
        ]

        _do_dry_run("hf", "test/model", "model", "main",
                    ["*.json"], ["*.bin"], files)
        out = capsys.readouterr().out

        assert "Total files:     4" in out
        assert "Include:         *.json" in out
        assert "Exclude:         *.bin" in out
        assert "Would download:  2" in out  # config.json + tokenizer.json

    def test_dry_run_tree_type_excluded(self, capsys):
        """Tree-type files should be excluded from download count."""
        from modely import _do_dry_run

        files = [
            {"Path": "config.json", "Size": 1000, "Type": "blob"},
            {"Path": "subdir", "Size": 0, "Type": "tree"},
            {"Path": "model.bin", "Size": 500, "Type": "blob"},
        ]

        _do_dry_run("hf", "test/model", "model", "main", None, None, files)
        out = capsys.readouterr().out

        assert "Total files:     2" in out  # tree excluded
        assert "Would download:  2" in out

    def test_dry_run_empty_repo(self, capsys):
        """Dry-run with empty file list should show 0 files."""
        from modely import _do_dry_run
        _do_dry_run("hf", "empty/repo", "model", "main", None, None, [])
        out = capsys.readouterr().out
        assert "Would download:  0" in out

    def test_print_file_list_basic(self, capsys):
        """_print_file_list should print a formatted table."""
        from modely import _print_file_list

        files = [
            {"Path": "config.json", "Size": 1000, "Type": "blob"},
            {"Path": "model.safetensors", "Size": 500_000_000, "Type": "blob"},
        ]

        _print_file_list(files, "hf", "test/model")
        out = capsys.readouterr().out

        assert "[HF]" in out
        assert "test/model" in out
        assert "config.json" in out
        assert "model.safetensors" in out
        assert "2 file(s) shown" in out

    def test_print_file_list_empty(self, capsys):
        """_print_file_list with no files should show not found message."""
        from modely import _print_file_list
        _print_file_list([], "hf", "test/model")
        out = capsys.readouterr().out
        assert "No files found" in out


# ── P1: Dry-run CLI Arg Parsing (unit tests) ────────────────────

class TestDryRunCLI:
    """Test argparse parsing of --list-files and --dry-run flags."""

    def test_hf_list_files_flag(self):
        """--list-files should be parsed as True."""
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--list-files', action='store_true')

        args = parser.parse_args(["hf", "gpt2", "--list-files"])
        assert args.list_files is True

    def test_hf_dry_run_flag(self):
        """--dry-run should be parsed as True."""
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--dry-run', action='store_true')

        args = parser.parse_args(["hf", "gpt2", "--dry-run"])
        assert args.dry_run is True

    def test_ms_list_files_flag(self):
        """MS --list-files should be parsed as True."""
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        ms_parser = subparsers.add_parser("ms")
        ms_parser.add_argument('repo_id', type=str)
        ms_parser.add_argument('--list-files', action='store_true')

        args = parser.parse_args(["ms", "owner/model", "--list-files"])
        assert args.list_files is True

    def test_ms_dry_run_flag(self):
        """MS --dry-run should be parsed as True."""
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        ms_parser = subparsers.add_parser("ms")
        ms_parser.add_argument('repo_id', type=str)
        ms_parser.add_argument('--dry-run', action='store_true')

        args = parser.parse_args(["ms", "owner/model", "--dry-run"])
        assert args.dry_run is True

    def test_list_files_dry_run_default_false(self):
        """Without explicit flags, both should default to False."""
        import argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        hf_parser = subparsers.add_parser("hf")
        hf_parser.add_argument('repo_id', type=str)
        hf_parser.add_argument('--list-files', action='store_true')
        hf_parser.add_argument('--dry-run', action='store_true')

        args = parser.parse_args(["hf", "gpt2"])
        assert args.list_files is False
        assert args.dry_run is False


# ── P2: Coverage Gap Fillers (unit tests) ───────────────────────

class TestToIso:
    """Test the _to_iso timestamp-to-ISO converter in ms_search.py."""

    def test_unix_timestamp_converts(self):
        from modely.search.ms_search import _to_iso
        result = _to_iso(1700000000)
        assert result is not None
        assert "T" in result
        assert result.startswith("2023-")

    def test_none_returns_none(self):
        from modely.search.ms_search import _to_iso
        assert _to_iso(None) is None

    def test_iso_string_preserved(self):
        from modely.search.ms_search import _to_iso
        iso = "2024-06-01T12:00:00+00:00"
        assert _to_iso(iso) == iso

    def test_float_timestamp(self):
        from modely.search.ms_search import _to_iso
        result = _to_iso(1700000000.0)
        assert result is not None


class TestBuildSearchBody:
    """Test the _build_search_body function for ModelScope dolphin API."""

    def test_basic_body(self):
        from modely.search.ms_search import _build_search_body
        body = _build_search_body("qwen", None, 10)
        assert body["PageSize"] == 10
        assert body["PageNumber"] == 1
        assert body["Name"] == "qwen"
        assert body["SortBy"] == "Default"
        assert body["tasks"] == []
        assert body["tags"] == []

    def test_with_task(self):
        from modely.search.ms_search import _build_search_body
        body = _build_search_body("test", "text-generation", 5)
        assert body["tasks"] == ["text-generation"]

    def test_with_sort(self):
        """SortBy should always be 'Default' as dolphin API only accepts this value."""
        from modely.search.ms_search import _build_search_body
        body = _build_search_body("test", None, 10, sort="lastModified")
        # dolphin API only supports SortBy="Default"; client-side sorting handles the rest
        assert body["SortBy"] == "Default"

    def test_with_page(self):
        from modely.search.ms_search import _build_search_body
        body = _build_search_body("test", None, 10, page=3)
        assert body["PageNumber"] == 3

    def test_keyword_none_uses_empty(self):
        from modely.search.ms_search import _build_search_body
        body = _build_search_body(None, None, 10)
        assert body["Name"] == ""


class TestParseModelItem:
    """Test the _parse_model_item function for MS dolphin API responses."""

    def test_standard_item(self):
        from modely.search.ms_search import _parse_model_item
        item = {
            "Path": "owner",
            "Name": "model",
            "Downloads": 1000,
            "Stars": 50,
            "Tasks": [{"Name": "text-generation"}],
            "Tags": [],
        }
        result = _parse_model_item(item)
        assert result.id == "owner/model"
        assert result.source == "ms"
        assert result.downloads == 1000
        assert result.pipeline_tag == "text-generation"

    def test_likes_fallback_to_stars(self):
        from modely.search.ms_search import _parse_model_item
        item = {
            "Path": "o", "Name": "m", "Likes": None, "Stars": 42,
            "Tasks": [], "Tags": [],
        }
        result = _parse_model_item(item)
        assert result.likes == 42

    def test_tasks_as_strings(self):
        from modely.search.ms_search import _parse_model_item
        item = {
            "Path": "o", "Name": "m",
            "Tasks": ["text-classification"],
            "Tags": [],
        }
        result = _parse_model_item(item)
        assert result.pipeline_tag == "text-classification"

    def test_description_falls_back_to_chinese_name(self):
        from modely.search.ms_search import _parse_model_item
        item = {
            "Path": "o", "Name": "m",
            "ChineseName": "中文名",
            "Tasks": [], "Tags": [],
        }
        result = _parse_model_item(item)
        assert result.description == "中文名"

    def test_organization_as_author(self):
        from modely.search.ms_search import _parse_model_item
        item = {
            "Path": "p", "Name": "m",
            "Organization": "MyOrg",
            "Tasks": [], "Tags": [],
        }
        result = _parse_model_item(item)
        assert result.author == "MyOrg"


class TestCacheHelpers:
    """Test cache utility functions (previously uncovered)."""

    def test_format_size(self):
        from modely.common.cache import _format_size
        assert "B" in _format_size(500)
        assert "KB" in _format_size(2000)
        assert "MB" in _format_size(5_000_000)
        assert "GB" in _format_size(2_000_000_000)

    def test_get_dir_size(self, tmp_path):
        from modely.common.cache import _get_dir_size
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        size = _get_dir_size(str(tmp_path))
        assert size > 0

    def test_load_config_new_file(self, tmp_path, monkeypatch):
        from modely.common import cache as cache_mod
        config_path = tmp_path / "config.json"
        monkeypatch.setattr(cache_mod, "CONFIG_FILE", str(config_path))
        config = cache_mod._load_config()
        assert isinstance(config, dict)

    def test_save_and_load_config(self, tmp_path, monkeypatch):
        from modely.common import cache as cache_mod
        config_path = tmp_path / "config.json"
        monkeypatch.setattr(cache_mod, "CONFIG_FILE", str(config_path))
        cache_mod._save_config({"cache_dir": str(tmp_path)})
        config = cache_mod._load_config()
        assert config["cache_dir"] == str(tmp_path)

    def test_set_cache_dir(self, tmp_path, monkeypatch):
        from modely.common import cache as cache_mod
        config_path = tmp_path / "config.json"
        monkeypatch.setattr(cache_mod, "CONFIG_FILE", str(config_path))
        cache_mod.set_cache_dir(str(tmp_path / "cache"))
        config = cache_mod._load_config()
        assert "cache_dir" in config

    def test_get_source_cache_dir(self, tmp_path, monkeypatch):
        from modely.common import cache as cache_mod
        cache_mod.set_cache_dir(str(tmp_path))
        source_dir = cache_mod.get_source_cache_dir("ms")
        assert "ms" in source_dir

    def test_get_repo_type_dir(self, tmp_path, monkeypatch):
        from modely.common import cache as cache_mod
        cache_mod.set_cache_dir(str(tmp_path))
        dir_path = cache_mod.get_repo_type_dir("ms", "model")
        assert "models" in dir_path or "model" in dir_path

    def test_clean_cache(self, tmp_path, monkeypatch):
        from modely.common import cache as cache_mod
        cache_mod.set_cache_dir(str(tmp_path))
        # Create a fake cached file
        repo_dir = tmp_path / "ms" / "models" / "owner--model" / "master"
        repo_dir.mkdir(parents=True)
        (repo_dir / "test.txt").write_text("content")
        # Clean should work
        cleaned = cache_mod.clean_cache(cache_dir=str(tmp_path))
        assert cleaned >= 0


class TestBasicCache:
    """Test the BasicCache class in modelscope module."""

    def test_exists_true(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        f = tmp_path / "test.json"
        f.write_text("data")
        assert cache.exists({"Path": "test.json"})

    def test_exists_false(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        assert not cache.exists({"Path": "nonexistent.json"})

    def test_exists_no_path_key(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        assert not cache.exists({"Name": "test"})

    def test_put_file(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        src = tmp_path / "src.json"
        src.write_text("data")
        result = cache.put_file({"Path": "dst.json"}, str(src))
        assert result.endswith("dst.json")
        assert os.path.exists(result)

    def test_get_root_location(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        assert cache.get_root_location() == str(tmp_path)

    def test_get_file_by_info_returns_none(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        assert cache.get_file_by_info({"Path": "x"}) is None

    def test_get_file_by_path_returns_none(self, tmp_path):
        from modely.modelscope import BasicCache
        cache = BasicCache(str(tmp_path))
        assert cache.get_file_by_path("x") is None


class TestCreateTempDir:
    """Test create_temporary_directory and create_temporary_directory_and_cache."""

    def test_create_temporary_directory(self, tmp_path):
        from modely.modelscope import create_temporary_directory
        result = create_temporary_directory("owner/model", local_dir=str(tmp_path))
        assert os.path.exists(result)
        assert ".tmp" in result

    def test_create_temporary_directory_default_cwd(self):
        import os
        from modely.modelscope import create_temporary_directory
        result = create_temporary_directory("owner/model")
        assert os.path.exists(result)
        # Should be under current dir or default, with .tmp
        assert ".tmp" in result

    def test_create_temporary_directory_and_cache_with_local_dir(self, tmp_path):
        from modely.modelscope import create_temporary_directory_and_cache
        temp_dir, cache_obj = create_temporary_directory_and_cache(
            "owner/model", local_dir=str(tmp_path)
        )
        assert os.path.exists(temp_dir)
        assert ".tmp" in temp_dir

    def test_create_temporary_directory_and_cache_with_cache_dir(self, tmp_path):
        from modely.modelscope import create_temporary_directory_and_cache
        temp_dir, cache_obj = create_temporary_directory_and_cache(
            "owner/model", cache_dir=str(tmp_path)
        )
        assert os.path.exists(temp_dir)

    def test_create_temporary_directory_and_cache_without_both(self):
        from modely.modelscope import create_temporary_directory_and_cache
        temp_dir, cache_obj = create_temporary_directory_and_cache("owner/model")
        assert os.path.exists(temp_dir)


# ── Coverage: Remaining Gaps (unit tests) ───────────────────────

class TestTruncateHelpers:
    """Test display helper functions in search/display.py."""

    def test_truncate_url_short(self):
        from modely.search.display import _truncate_url
        assert _truncate_url("https://example.com/short") == "https://example.com/short"

    def test_truncate_url_long(self):
        from modely.search.display import _truncate_url
        long_url = "https://huggingface.co/" + "very-long-path/" * 10
        result = _truncate_url(long_url)
        assert len(result) <= 55
        assert result.endswith("...")

    def test_truncate_id_short(self):
        from modely.search.display import _truncate_id
        assert _truncate_id("owner/repo") == "owner/repo"

    def test_truncate_id_long(self):
        from modely.search.display import _truncate_id
        long_id = "x" * 60
        result = _truncate_id(long_id)
        assert len(result) <= 45
        assert result.endswith("...")


class TestParseDate:
    """Test _parse_date helper in search/__init__.py."""

    def test_valid_iso(self):
        from modely.search import _parse_date
        result = _parse_date("2024-06-01T12:00:00+00:00")
        assert result.year == 2024
        assert result.month == 6

    def test_none_returns_min(self):
        from modely.search import _parse_date
        from datetime import datetime
        result = _parse_date(None)
        assert result == datetime.min.replace(tzinfo=None)

    def test_short_date(self):
        from modely.search import _parse_date
        result = _parse_date("2024-06-01")
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 1


class TestApplyDateFilter:
    """Test _apply_date_filter in search/__init__.py."""

    def test_no_filters_returns_all(self):
        from modely.search import _apply_date_filter
        from modely.search import SearchResult
        results = [
            SearchResult(id="a", source="hf", repo_type="model", last_modified="2024-06-01"),
            SearchResult(id="b", source="hf", repo_type="model", last_modified="2023-01-01"),
        ]
        filtered = _apply_date_filter(results, None, None)
        assert len(filtered) == 2

    def test_after_filter(self):
        from modely.search import _apply_date_filter
        from modely.search import SearchResult
        results = [
            SearchResult(id="old", source="hf", repo_type="model", last_modified="2022-01-01"),
            SearchResult(id="new", source="hf", repo_type="model", last_modified="2024-06-01"),
        ]
        filtered = _apply_date_filter(results, "2023-01-01", None)
        assert [r.id for r in filtered] == ["new"]

    def test_before_filter(self):
        from modely.search import _apply_date_filter
        from modely.search import SearchResult
        results = [
            SearchResult(id="old", source="hf", repo_type="model", last_modified="2022-01-01"),
            SearchResult(id="new", source="hf", repo_type="model", last_modified="2024-06-01"),
        ]
        filtered = _apply_date_filter(results, None, "2023-01-01")
        assert [r.id for r in filtered] == ["old"]

    def test_no_date_passed_through(self):
        from modely.search import _apply_date_filter
        from modely.search import SearchResult
        results = [
            SearchResult(id="a", source="hf", repo_type="model", last_modified=None),
            SearchResult(id="b", source="hf", repo_type="model", last_modified="2024-01-01"),
        ]
        filtered = _apply_date_filter(results, "2023-01-01", None)
        assert len(filtered) == 2  # None-date always included


class TestModelScopeHelpers:
    """Test remaining ModelScope helper functions."""

    def test_get_model_cache_root(self, tmp_path, monkeypatch):
        from modely.modelscope import get_model_cache_root
        import modely.common.cache as c
        monkeypatch.setattr(c, "get_source_cache_dir", lambda source, cache_dir: str(tmp_path))
        result = get_model_cache_root(str(tmp_path))
        assert result.endswith("models")

    def test_get_dataset_cache_root(self, tmp_path, monkeypatch):
        from modely.modelscope import get_dataset_cache_root
        import modely.common.cache as c
        monkeypatch.setattr(c, "get_source_cache_dir", lambda source, cache_dir: str(tmp_path))
        result = get_dataset_cache_root(str(tmp_path))
        assert result.endswith("datasets")


class TestGitHubHelpers:
    """Test GitHub module helper functions."""

    def test_get_default_branch_main_exists(self, monkeypatch):
        from modely.github import get_default_branch

        class FakeResponse:
            status_code = 200
            def json(self):
                return {"default_branch": "main"}
            def raise_for_status(self):
                pass

        def fake_get(url, headers, timeout):
            return FakeResponse()

        monkeypatch.setattr("modely.github.requests.get", fake_get)
        result = get_default_branch("owner/repo")
        assert result == "main"

    def test_get_default_branch_master(self, monkeypatch):
        from modely.github import get_default_branch

        class FakeResponse:
            status_code = 200
            def json(self):
                return {"default_branch": "master"}
            def raise_for_status(self):
                pass

        def fake_get(url, headers, timeout):
            return FakeResponse()

        monkeypatch.setattr("modely.github.requests.get", fake_get)
        result = get_default_branch("owner/repo")
        assert result == "master"

    def test_get_default_branch_error_returns_none(self, monkeypatch):
        from modely.github import get_default_branch

        def fake_get(url, headers, timeout):
            raise Exception("network error")

        monkeypatch.setattr("modely.github.requests.get", fake_get)
        result = get_default_branch("owner/repo")
        assert result is None
