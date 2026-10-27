"""Download planning application services."""

from __future__ import annotations

import json
import os
from typing import Optional, List

from ..common import cache
from .file_queries import filter_files, format_file_size, list_repo_files, summarize_files
from .download_profiles import resolve_download_profile
from ..types import DownloadPlan
from ..uri import concrete_repo_type, normalize_repo_type, normalize_source, parse_modely_uri

_LARGE_FILE_COUNT = 1000
_LARGE_SIZE_BYTES = 10_000_000_000


def create_download_plan(
    resource: str,
    *,
    source: str = "auto",
    repo_type: str = "model",
    revision: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    profile: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    cache_dir: Optional[str] = None,
    local_dir: Optional[str] = None,
    release: Optional[str] = None,
    list_repo_files_func=None,
) -> DownloadPlan:
    """Create a dry-run plan describing files selected for download."""
    warnings = []
    if "://" in resource:
        ref = parse_modely_uri(resource)
    else:
        if source == "auto":
            source = "hf"
            warnings.append("Plain repository IDs default to Hugging Face for planning; pass --source to plan another source.")
        ref = parse_modely_uri(resource, source=normalize_source(source), repo_type=concrete_repo_type(repo_type, source))
    if revision:
        ref.revision = revision

    include, exclude = resolve_download_profile(profile, include, exclude)
    if list_repo_files_func is None:
        list_repo_files_func = list_repo_files
    files = list_repo_files_func(ref, revision=ref.revision, token=token, endpoint=endpoint, release=release)
    selected = filter_files(files, include, exclude)
    summary = summarize_files(files, include, exclude)
    warnings.extend(_preflight_warnings(summary, include=include, exclude=exclude, profile=profile))
    cache_hits = _estimate_cache_hits(ref.source, ref.repo_type, ref.repo_id, ref.revision, selected, cache_dir, local_dir)
    return DownloadPlan(
        source=ref.source,
        repo_type=ref.repo_type,
        repo_id=ref.repo_id,
        revision=ref.revision,
        include=include,
        exclude=exclude,
        profile=profile,
        files=selected,
        summary=summary,
        cache_dir=cache.get_cache_dir(cache_dir),
        local_dir=local_dir,
        cache_hits=cache_hits,
        cache_misses=max(0, len(selected) - cache_hits),
        warnings=warnings,
        metadata={"release": release} if release else {},
    )


def print_download_plan(plan: DownloadPlan, *, as_json: bool = False) -> None:
    """Print a download plan."""
    if as_json:
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Source:        {plan.source}")
    print(f"Repo type:     {plan.repo_type}")
    print(f"Repo ID:       {plan.repo_id}")
    if plan.revision:
        print(f"Revision:      {plan.revision}")
    if plan.profile:
        print(f"Profile:       {plan.profile}")
    if plan.include:
        print(f"Include:       {' '.join(plan.include)}")
    if plan.exclude:
        print(f"Exclude:       {' '.join(plan.exclude)}")
    if plan.summary:
        print(f"Total files:   {plan.summary.total_files} ({format_file_size(plan.summary.total_size)})")
        print(f"Selected:      {plan.summary.selected_files} ({format_file_size(plan.summary.selected_size)})")
        if plan.summary.categories:
            print("Categories:")
            for name in sorted(plan.summary.categories):
                print(f"  - {name}: {plan.summary.categories[name]} ({format_file_size(plan.summary.category_sizes.get(name, 0))})")
    print(f"Cache hits:    {plan.cache_hits}")
    print(f"Cache misses:  {plan.cache_misses}")
    if plan.local_dir:
        print(f"Local dir:     {plan.local_dir}")
    else:
        print(f"Cache dir:     {plan.cache_dir}")
    for warning in plan.warnings:
        print(f"Warning: {warning}")


def _preflight_warnings(summary, *, include=None, exclude=None, profile=None) -> list[str]:
    """Return download-before-confirmation warnings for large selections."""
    if not summary:
        return []
    warnings = []
    has_selection = bool(include or exclude or profile)
    if summary.selected_files >= _LARGE_FILE_COUNT and not has_selection:
        warnings.append(
            f"Large selection: {summary.selected_files} files selected. "
            "Consider --include/--exclude or --profile before downloading."
        )
    if summary.selected_size >= _LARGE_SIZE_BYTES and not has_selection:
        warnings.append(
            f"Large download: {format_file_size(summary.selected_size)} selected. "
            "Use filters or a profile to avoid downloading unnecessary files."
        )
    return warnings


def _estimate_cache_hits(source, repo_type, repo_id, revision, files, cache_dir, local_dir) -> int:
    hits = 0
    revision = revision or ("main" if source in {"hf", "github"} else "master")
    for f in files:
        candidates = []
        if local_dir:
            candidates.append(os.path.join(local_dir, f.path))
        try:
            candidates.append(cache.get_file_path(repo_id, f.path, revision, repo_type, source, cache_dir))
        except Exception:
            pass
        if any(os.path.exists(path) for path in candidates):
            hits += 1
    return hits


__all__ = ["create_download_plan", "print_download_plan"]
