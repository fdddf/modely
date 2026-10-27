"""
Unified cache management for modely-ai.

Provides a unified cache system for storing and managing downloaded models/datasets
from Hugging Face and ModelScope, avoiding duplicate downloads.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict


CONFIG_DIR = os.path.join(str(Path.home()), ".modely")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_CACHE_DIR = os.path.join(str(Path.home()), ".cache", "modely")

# Cache structure constants
SOURCE_HF = "hf"
SOURCE_MS = "ms"
SOURCE_GITHUB = "github"
REPO_TYPE_MODEL = "models"
REPO_TYPE_DATASET = "datasets"
REPO_TYPE_TOOL = "tools"


def _load_config() -> Dict:
    """Load configuration from config file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_config(config: Dict) -> None:
    """Save configuration to config file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_cache_dir(explicit_dir: Optional[str] = None) -> str:
    """
    Resolve the cache directory with priority:
    1. Explicit directory argument
    2. Environment variable MODELY_CACHE
    3. Config file setting
    4. Default: ~/.cache/modely
    """
    if explicit_dir:
        cache_dir = explicit_dir
    elif os.environ.get("MODELY_CACHE"):
        cache_dir = os.environ.get("MODELY_CACHE")
    else:
        config = _load_config()
        cache_dir = config.get("cache_dir", DEFAULT_CACHE_DIR)

    os.makedirs(cache_dir, exist_ok=True)
    return os.path.abspath(cache_dir)


def set_cache_dir(cache_dir: str) -> None:
    """Set the cache directory in config file."""
    config = _load_config()
    config["cache_dir"] = os.path.abspath(cache_dir)
    _save_config(config)


def get_source_cache_dir(source: str, cache_dir: Optional[str] = None) -> str:
    """Get cache directory for a specific source (hf or ms)."""
    base = get_cache_dir(cache_dir)
    path = os.path.join(base, source)
    os.makedirs(path, exist_ok=True)
    return path


def _repo_type_to_dir(repo_type: str) -> str:
    """Convert repo_type string to directory name."""
    mapping = {
        "model": REPO_TYPE_MODEL,
        "dataset": REPO_TYPE_DATASET,
        "tool": REPO_TYPE_TOOL,
    }
    return mapping.get(repo_type, repo_type)


def get_repo_type_dir(source: str, repo_type: str, cache_dir: Optional[str] = None) -> str:
    """Get cache directory for a specific source and repo type."""
    source_dir = get_source_cache_dir(source, cache_dir)
    type_dir = _repo_type_to_dir(repo_type)
    path = os.path.join(source_dir, type_dir)
    os.makedirs(path, exist_ok=True)
    return path


def get_repo_cache_dir(repo_id: str, repo_type: str, revision: str, source: str,
                       cache_dir: Optional[str] = None) -> str:
    """Get cache directory for a specific repo and revision."""
    type_dir = get_repo_type_dir(source, repo_type, cache_dir)
    # Normalize repo_id for filesystem (replace / with --)
    repo_dir_name = repo_id.replace("/", "--")
    repo_path = os.path.join(type_dir, repo_dir_name, revision)
    os.makedirs(repo_path, exist_ok=True)
    return repo_path


def get_file_path(repo_id: str, filename: str, revision: str, repo_type: str,
                  source: str, cache_dir: Optional[str] = None) -> str:
    """Compute the expected cache file path."""
    repo_cache_dir = get_repo_cache_dir(repo_id, repo_type, revision, source, cache_dir)
    return os.path.join(repo_cache_dir, filename)


def is_cached(repo_id: str, filename: str, revision: str, repo_type: str,
              source: str, cache_dir: Optional[str] = None) -> bool:
    """Check if a file exists in cache and is non-empty."""
    file_path = get_file_path(repo_id, filename, revision, repo_type, source, cache_dir)
    return os.path.exists(file_path) and os.path.getsize(file_path) > 0


def get_cached_repo_path(repo_id: str, repo_type: str, revision: str, source: str,
                         cache_dir: Optional[str] = None) -> Optional[str]:
    """Get the cached repo directory if it exists, otherwise return None."""
    repo_dir = get_repo_cache_dir(repo_id, repo_type, revision, source, cache_dir)
    if os.path.exists(repo_dir) and os.listdir(repo_dir):
        return repo_dir
    return None


def _get_dir_size(path: str) -> int:
    """Calculate total size of a directory."""
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += _get_dir_size(entry.path)
    return total


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def cache_info(cache_dir: Optional[str] = None) -> Dict:
    """Get cache information: directory path and total size."""
    cache_dir = get_cache_dir(cache_dir)
    total_size = 0
    if os.path.exists(cache_dir):
        total_size = _get_dir_size(cache_dir)

    return {
        "cache_dir": cache_dir,
        "total_size": total_size,
        "total_size_str": _format_size(total_size),
        "config_file": CONFIG_FILE,
    }


def list_cache(cache_dir: Optional[str] = None, detail: bool = False) -> List[Dict]:
    """
    List all cached repositories and files.

    Returns a list of dicts with keys:
    - source: 'hf' or 'ms'
    - repo_type: 'models' or 'datasets'
    - repo_id: original repo ID
    - revision: revision string
    - path: filesystem path
    - size: total size in bytes
    - files: list of files (if detail=True)
    """
    cache_dir = get_cache_dir(cache_dir)
    results = []

    for source in [SOURCE_HF, SOURCE_MS, SOURCE_GITHUB]:
        source_dir = os.path.join(cache_dir, source)
        if not os.path.exists(source_dir):
            continue

        for repo_type_dir in os.listdir(source_dir):
            type_path = os.path.join(source_dir, repo_type_dir)
            if not os.path.isdir(type_path):
                continue

            for repo_dir in os.listdir(type_path):
                repo_path = os.path.join(type_path, repo_dir)
                if not os.path.isdir(repo_path):
                    continue

                # repo_dir is repo_id with / replaced by --
                repo_id = repo_dir.replace("--", "/")

                for revision in os.listdir(repo_path):
                    rev_path = os.path.join(repo_path, revision)
                    if not os.path.isdir(rev_path):
                        continue

                    size = _get_dir_size(rev_path)
                    entry = {
                        "source": source,
                        "repo_type": repo_type_dir.rstrip("s"),  # models->model
                        "repo_id": repo_id,
                        "revision": revision,
                        "path": rev_path,
                        "size": size,
                        "size_str": _format_size(size),
                    }

                    if detail:
                        files = []
                        for root, _, filenames in os.walk(rev_path):
                            for fname in filenames:
                                fpath = os.path.join(root, fname)
                                rel_path = os.path.relpath(fpath, rev_path)
                                files.append({
                                    "name": rel_path,
                                    "size": os.path.getsize(fpath),
                                    "size_str": _format_size(os.path.getsize(fpath)),
                                })
                        entry["files"] = files

                    results.append(entry)

    return results


def clean_cache(repo_id: Optional[str] = None, repo_type: Optional[str] = None,
                source: Optional[str] = None, revision: Optional[str] = None,
                cache_dir: Optional[str] = None) -> int:
    """
    Clean cache.

    Args:
        repo_id: If provided, only clean this repo. Otherwise clean all.
        repo_type: Filter by repo type ('model' or 'dataset')
        source: Filter by source ('hf' or 'ms')
        revision: Filter by revision
        cache_dir: Override cache directory

    Returns:
        Number of bytes cleaned
    """
    cache_dir = get_cache_dir(cache_dir)
    cleaned_bytes = 0

    if repo_id:
        # Clean specific repo
        for src in ([source] if source else [SOURCE_HF, SOURCE_MS, SOURCE_GITHUB]):
            for rtype in ([repo_type] if repo_type else ["model", "dataset", "tool"]):
                for rev in ([revision] if revision else ["*"]):
                    if rev == "*":
                        # Get all revisions for this repo
                        type_dir = get_repo_type_dir(src, rtype, cache_dir)
                        repo_dir_name = repo_id.replace("/", "--")
                        repo_path = os.path.join(type_dir, repo_dir_name)
                        if os.path.exists(repo_path):
                            for rev_dir in os.listdir(repo_path):
                                rev_path = os.path.join(repo_path, rev_dir)
                                if os.path.isdir(rev_path):
                                    size = _get_dir_size(rev_path)
                                    shutil.rmtree(rev_path)
                                    cleaned_bytes += size
                    else:
                        repo_cache = get_repo_cache_dir(repo_id, rtype, rev, src, cache_dir)
                        if os.path.exists(repo_cache):
                            size = _get_dir_size(repo_cache)
                            shutil.rmtree(repo_cache)
                            cleaned_bytes += size
    else:
        # Clean all cache
        if os.path.exists(cache_dir):
            cleaned_bytes = _get_dir_size(cache_dir)
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir, exist_ok=True)

    return cleaned_bytes
