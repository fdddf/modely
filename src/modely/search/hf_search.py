"""Hugging Face search backend for modely-ai."""

from typing import List, Optional

from huggingface_hub import HfApi

from .types import SearchResult


# Map our sort field names to huggingface_hub sort values
_SORT_MAP = {
    "downloads": "downloads",
    "lastModified": "last_modified",
    "likes": "likes",
    "created_at": "created_at",
}


def search_huggingface(
    keyword: Optional[str] = None,
    *,
    repo_type: str = "model",
    task: Optional[str] = None,
    library: Optional[str] = None,
    license: Optional[str] = None,
    sort: str = "downloads",
    direction: str = "desc",
    limit: int = 20,
    author: Optional[str] = None,
    full: bool = True,  # default True: need author, license tags, last_modified, etc.
) -> List[SearchResult]:
    """Search Hugging Face Hub for models or datasets.

    Uses the official ``huggingface_hub`` SDK for reliable access.
    """
    api = HfApi()

    # Build filter list for pipeline_tag / library / license
    filters = []
    if task:
        filters.append(task)
    if library:
        filters.append(library)
    if license:
        filters.append(f"license:{license}")

    hf_sort = _SORT_MAP.get(sort, "downloads")

    output: List[SearchResult] = []

    try:
        list_fn = api.list_datasets if repo_type == "dataset" else api.list_models

        items = list_fn(
            filter=filters if filters else None,
            search=keyword if keyword else None,
            author=author,
            sort=hf_sort,
            limit=limit,
            full=True,  # full metadata: author, license, description, last_modified, siblings
        )

        for item in items:
            # Extract fields safely across model/dataset info types
            last_modified = getattr(item, "last_modified", None)
            if last_modified and hasattr(last_modified, "isoformat"):
                last_modified = last_modified.isoformat()

            created_at = getattr(item, "created_at", None)
            if created_at and hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()

            tags_raw = getattr(item, "tags", None) or []
            if isinstance(tags_raw, list):
                tags = [str(t) for t in tags_raw if t is not None]
            else:
                tags = []

            # Extract license from tags (e.g. "license:apache-2.0") — HF list API
            # does not include a top-level license field even with full=True.
            license_val = None
            for t in tags:
                if t.startswith("license:") or t.startswith("License:"):
                    license_val = t.split(":", 1)[1].strip()
                    break

            # Description: try card_data first, then HF list API might expose it
            # via a nested attribute on some SDK versions.
            description = None
            card_data = getattr(item, "card_data", None)
            if card_data is not None:
                description = getattr(card_data, "description", None) or getattr(card_data, "summary", None)
            if not description:
                description = getattr(item, "description", None)

            result = SearchResult(
                id=getattr(item, "id", ""),
                source="hf",
                repo_type=repo_type,
                url=_hf_repo_url(getattr(item, "id", ""), repo_type),
                author=getattr(item, "author", None),
                downloads=getattr(item, "downloads", 0) or 0,
                likes=getattr(item, "likes", 0) or 0,
                last_modified=last_modified,
                created_at=created_at,
                pipeline_tag=getattr(item, "pipeline_tag", None),
                library_name=getattr(item, "library_name", None),
                tags=tags,
                license=license_val,
                description=description,
                size_bytes=_siblings_size(getattr(item, "siblings", None)),
                metadata={"backend": "huggingface_hub"},
            )
            output.append(result)

        # huggingface_hub always returns descending by numeric fields.
        # Reverse client-side when ascending is requested.
        if direction == "asc":
            output.reverse()

    except Exception as e:
        import sys

        print(f"Warning: Hugging Face search failed: {e}", file=sys.stderr)

    return output


def _hf_repo_url(repo_id: str, repo_type: str) -> str:
    """Return the canonical Hugging Face web URL for a repository type."""
    prefix = "datasets/" if repo_type == "dataset" else "spaces/" if repo_type == "space" else ""
    return f"https://huggingface.co/{prefix}{repo_id}"


def _siblings_size(siblings) -> int:
    """Best-effort total size from HF sibling metadata."""
    total = 0
    for sibling in siblings or []:
        size = getattr(sibling, "size", None)
        if isinstance(size, int):
            total += size
    return total
