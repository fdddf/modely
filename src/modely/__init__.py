"""Public API and compatibility layer for modely-ai."""

from __future__ import annotations

import sys

from .cli import main
from .cli.handlers import cache_main
from .modelscope import (
    main as modelscope_main,
    model_file_download,
    dataset_file_download,
    snapshot_download as modelscope_snapshot_download,
    HubApi,
)
from .hf import hf_file_download, snapshot_download as hf_snapshot_download, main as hf_main
from .github import github_file_download, snapshot_download as github_snapshot_download, main as github_main
from .watch import main as watch_main, run_watch, list_targets as watch_list_targets
from .search import SearchResult, main as search_main
from .files import do_dry_run, format_file_size, list_repo_files, print_file_list
from .get import download_resource
from .resolve import print_resolve_result, resolve_resource
from .score import print_asset_score, score_path, score_resource
from .scan import print_scan_result, scan_path, scan_resource
from .catalog import print_catalog_report, scan_catalog
from .compare import compare_resources
from .manifest import create_lock, install_lock, validate_lock
from .mirror import verify_mirror
from .choose import choose_resource
from .sources import list_source_profiles, rank_sources
from .info import get_repo_info
from .common import cache


# Stable public Python API aliases. Avoid aliases that shadow submodules such as
# modely.scan or modely.compare so monkeypatching and module imports stay compatible.
download = download_resource
catalog_scan = scan_catalog


def _format_file_size(size_bytes):
    """Format bytes into human-readable form."""
    return format_file_size(size_bytes)


def _print_file_list(files, source, repo_id):
    """Print a formatted table of repository files."""
    print_file_list(files, source, repo_id)


def _do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files):
    """Simulate what would be downloaded and print a summary."""
    do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files)


def _list_hf_files(repo_id, repo_type, revision, token, endpoint):
    """Fetch file listing from Hugging Face Hub."""
    from .hf import list_files
    try:
        files = list_files(repo_id, repo_type=repo_type, revision=revision, token=token, endpoint=endpoint)
        return [f.to_dict() | {"Path": f.path, "Size": f.size, "Type": f.type} for f in files]
    except Exception as e:
        print(f"Warning: Could not list files from HF: {e}", file=sys.stderr)
        return []


def _list_ms_files(repo_id, repo_type, revision, token):
    """Fetch file listing from ModelScope."""
    from .modelscope import HubApi
    api = HubApi(token=token)
    try:
        if repo_type == "model":
            files = api.get_model_files(repo_id, revision=revision)
        else:
            files = api.get_dataset_files(repo_id, revision=revision)
        return files
    except Exception as e:
        print(f"Warning: Could not list files from ModelScope: {e}", file=sys.stderr)
        return []


__all__ = [
    "main",
    "model_file_download",
    "dataset_file_download",
    "modelscope_snapshot_download",
    "hf_file_download",
    "hf_snapshot_download",
    "github_file_download",
    "github_snapshot_download",
    "HubApi",
    "cache",
    "cache_main",
    "watch_main",
    "run_watch",
    "watch_list_targets",
    "SearchResult",
    "search_main",
    "download",
    "download_resource",
    "resolve_resource",
    "print_resolve_result",
    "compare_resources",
    "verify_mirror",
    "scan_resource",
    "scan_path",
    "print_scan_result",
    "score_resource",
    "score_path",
    "print_asset_score",
    "create_lock",
    "install_lock",
    "validate_lock",
    "catalog_scan",
    "scan_catalog",
    "print_catalog_report",
    "choose_resource",
    "list_source_profiles",
    "rank_sources",
    "get_repo_info",
    "list_repo_files",
]
