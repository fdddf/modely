"""Kaggle dataset/competition backend.

This module lazy-loads the optional Kaggle API so modely-ai does not require it
unless Kaggle support is used.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from modely.common import cache
from modely.types import FileInfo, RepoInfo


def _api():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except Exception as exc:
        raise ImportError("Kaggle support requires the optional 'kaggle' package and configured credentials. Install with: pip install kaggle") from exc
    api = KaggleApi()
    api.authenticate()
    return api


def search_kaggle(keyword=None, *, repo_type="dataset", limit=20):
    """Search Kaggle datasets."""
    if repo_type not in {"dataset", "competition"}:
        return []
    api = _api()
    if repo_type == "competition":
        items = api.competitions_list(search=keyword)[:limit]
    else:
        items = api.dataset_list(search=keyword)[:limit]
    return items[:limit]


def kaggle_repo_info(repo_id: str, *, repo_type="dataset", revision=None, token=None) -> RepoInfo:
    """Return best-effort Kaggle metadata."""
    files = []
    try:
        files = kaggle_list_files(repo_id, repo_type=repo_type)
    except Exception:
        files = []
    if repo_type == "competition":
        url = f"https://www.kaggle.com/competitions/{repo_id}"
        author = None
    else:
        url = f"https://www.kaggle.com/datasets/{repo_id}"
        author = repo_id.split("/", 1)[0] if "/" in repo_id else None
    return RepoInfo(
        source="kaggle",
        repo_type=repo_type,
        repo_id=repo_id,
        url=url,
        author=author,
        revision=revision,
        metadata={"file_count": len(files)},
    )


def kaggle_list_files(repo_id: str, *, repo_type="dataset", revision=None, token=None) -> list[FileInfo]:
    """List Kaggle dataset or competition files."""
    api = _api()
    if repo_type == "competition":
        raw = api.competition_list_files(repo_id)
    else:
        raw = api.dataset_list_files(repo_id).files
    result = []
    for item in raw:
        name = getattr(item, "name", None) or getattr(item, "ref", None) or str(item)
        size = getattr(item, "totalBytes", None) or getattr(item, "size", 0) or 0
        result.append(FileInfo(path=name, size=size, type="blob", metadata={"raw": repr(item)}))
    return result


def kaggle_download(repo_id: str, *, repo_type="dataset", file: Optional[str] = None,
                    local_dir=None, cache_dir=None, force_download=False) -> str:
    """Download a Kaggle dataset/competition or a single file."""
    api = _api()
    revision = "latest"
    target_dir = local_dir or cache.get_repo_cache_dir(repo_id, repo_type, revision, "kaggle", cache_dir)
    os.makedirs(target_dir, exist_ok=True)
    if file:
        if repo_type == "competition":
            api.competition_download_file(repo_id, file, path=target_dir, force=force_download, quiet=False)
        else:
            api.dataset_download_file(repo_id, file, path=target_dir, force=force_download, quiet=False)
        return str(Path(target_dir) / file)
    if repo_type == "competition":
        api.competition_download_files(repo_id, path=target_dir, force=force_download, quiet=False)
    else:
        api.dataset_download_files(repo_id, path=target_dir, force=force_download, quiet=False, unzip=False)
    return str(target_dir)
