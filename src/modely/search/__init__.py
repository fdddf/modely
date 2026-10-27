"""
Search module for modely-ai — unified model and dataset discovery across
Hugging Face, ModelScope, and GitHub.
"""

import json
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from .types import SearchResult
from .hf_search import search_huggingface
from .ms_search import search_modelscope
from .gh_search import search_github
from .kaggle_search import search_kaggle
from .display import format_table, format_json
from .dedupe import dedupe_results, format_grouped_json, format_grouped_table
from ..uri import repo_type_candidates


# Sort field mapping for cross-platform result sorting
_SORT_KEY_MAP = {
    "downloads": lambda r: (r.downloads or 0),
    "likes": lambda r: (r.likes or 0),
    "lastModified": lambda r: _parse_date(r.last_modified),
    "created_at": lambda r: _parse_date(r.created_at),
}


def _parse_date(date_str: Optional[str]) -> datetime:
    """Parse an ISO date string into a datetime for sorting; epoch for None."""
    if not date_str:
        return datetime.min.replace(tzinfo=None)
    try:
        s = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=None)


def _apply_date_filter(
    results: List[SearchResult], after: Optional[str], before: Optional[str]
) -> List[SearchResult]:
    """Client-side date filtering since neither API supports it natively."""
    if not after and not before:
        return results

    after_dt = _parse_date(after) if after else None
    before_dt = _parse_date(before) if before else None

    filtered = []
    for r in results:
        dt = _parse_date(r.last_modified)
        if dt == datetime.min.replace(tzinfo=None):
            filtered.append(r)  # no date info, include it
            continue
        if after_dt and dt < after_dt:
            continue
        if before_dt and dt > before_dt:
            continue
        filtered.append(r)
    return filtered


def search(
    keyword: Optional[str] = None,
    *,
    source: str = "all",
    repo_type: str = "model",
    task: Optional[str] = None,
    library: Optional[str] = None,
    license: Optional[str] = None,
    sort: str = "downloads",
    direction: str = "desc",
    limit: int = 20,
    author: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    full: bool = False,
) -> List[SearchResult]:
    """Search for models/datasets across Hugging Face and/or ModelScope.

    Args:
        keyword: Search keyword to match repository names.
        source: Platform to search — ``"hf"``, ``"ms"``, or ``"all"`` (default).
        repo_type: ``"model"`` or ``"dataset"``.
        task: Filter by task type (e.g. ``"text-classification"``).
        library: Filter by library (HF only, e.g. ``"transformers"``).
        license: Filter by license name (HF only).
        sort: Sort field — ``"downloads"``, ``"lastModified"``, ``"likes"``, ``"created_at"``.
        direction: ``"asc"`` or ``"desc"``.
        limit: Maximum results per source.
        author: Filter by author/owner name.
        after: Only include results modified after this ISO 8601 / ``YYYY-MM-DD`` date.
        before: Only include results modified before this date.
        full: Request full model/dataset metadata (HF only; slower).

    Returns:
        List of ``SearchResult`` objects.
    """

    def _fetch_for_repo_types(source_name, fetch):
        results = []
        for candidate_type in repo_type_candidates(repo_type, source_name):
            results.extend(fetch(candidate_type))
        return results

    def _fetch_hf():
        return _fetch_for_repo_types("hf", lambda candidate_type: search_huggingface(
            keyword=keyword,
            repo_type=candidate_type,
            task=task,
            library=library,
            license=license,
            sort=sort,
            direction=direction,
            limit=limit,
            author=author,
            full=full,
        ))

    def _fetch_ms():
        if library:
            warnings.warn("--library filter is not supported on ModelScope, ignoring.")
        if license:
            warnings.warn("--license filter is not supported on ModelScope, ignoring.")
        return _fetch_for_repo_types("ms", lambda candidate_type: search_modelscope(
            keyword=keyword,
            repo_type=candidate_type,
            task=task,
            sort=sort,
            direction=direction,
            limit=limit,
        ))

    def _fetch_gh():
        if library:
            warnings.warn("--library filter is not supported on GitHub, ignoring.")
        if license:
            warnings.warn("--license filter is not supported on GitHub, ignoring.")
        return search_github(
            keyword=keyword,
            sort=sort,
            direction=direction,
            limit=limit,
        )

    def _fetch_kg():
        if library:
            warnings.warn("--library filter is not supported on Kaggle, ignoring.")
        if license:
            warnings.warn("--license filter is not supported on Kaggle, ignoring.")
        return search_kaggle(keyword=keyword, repo_type=repo_type_candidates(repo_type, "kaggle")[0], limit=limit)

    all_results: List[SearchResult] = []

    if source == "all":
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_fetch_hf): "hf",
                executor.submit(_fetch_ms): "ms",
                executor.submit(_fetch_gh): "github",
                executor.submit(_fetch_kg): "kaggle",
            }
            for future in as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass  # error already printed by backend
    elif source == "hf":
        all_results = _fetch_hf()
    elif source == "ms":
        all_results = _fetch_ms()
    elif source == "github":
        all_results = _fetch_gh()
    elif source == "kaggle":
        all_results = _fetch_kg()
    else:
        raise ValueError(f"Unknown source: {source}")

    # Apply client-side date filtering
    all_results = _apply_date_filter(all_results, after, before)

    # Sort merged results
    sort_fn = _SORT_KEY_MAP.get(sort, _SORT_KEY_MAP["downloads"])
    reverse = direction == "desc"
    all_results.sort(key=sort_fn, reverse=reverse)

    return all_results


def main(args) -> None:
    """CLI entry point for ``modely-ai search``.

    Accepts an ``argparse.Namespace`` (passed from ``modely/__init__.py``).
    """
    try:
        results = search(
            keyword=args.keyword,
            source=getattr(args, "source", "all"),
            repo_type=getattr(args, "repo_type", "model"),
            task=args.task,
            library=args.library,
            license=args.license,
            sort=args.sort,
            direction=args.direction,
            limit=args.limit,
            author=args.author,
            after=args.after,
            before=args.before,
            full=getattr(args, "full", False),
        )

        if getattr(args, "dedupe", False) or getattr(args, "compare", False):
            groups = dedupe_results(results)
            if args.json:
                print(format_grouped_json(groups))
            else:
                print(format_grouped_table(groups, compare=getattr(args, "compare", False)))
        elif args.json:
            print(format_json(results))
        else:
            print(format_table(results))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


__all__ = ["search", "search_huggingface", "search_modelscope", "search_github", "SearchResult", "main"]
