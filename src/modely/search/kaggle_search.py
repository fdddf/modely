"""Kaggle search adapter."""

from __future__ import annotations

from .types import SearchResult


def search_kaggle(keyword=None, *, repo_type="dataset", limit=20):
    """Search Kaggle and normalize results."""
    from modely.kaggle import search_kaggle as _search
    items = _search(keyword=keyword, repo_type=repo_type, limit=limit)
    results = []
    for item in items:
        ref = getattr(item, "ref", None) or getattr(item, "datasetRef", None) or getattr(item, "title", "")
        title = getattr(item, "title", None) or ref
        owner = getattr(item, "ownerName", None) or (ref.split("/", 1)[0] if "/" in ref else None)
        url = getattr(item, "url", None) or (f"https://www.kaggle.com/datasets/{ref}" if repo_type == "dataset" else f"https://www.kaggle.com/competitions/{ref}")
        results.append(SearchResult(
            id=ref or title,
            source="kaggle",
            repo_type=repo_type,
            url=url,
            author=owner,
            downloads=getattr(item, "downloadCount", 0) or 0,
            likes=getattr(item, "voteCount", 0) or 0,
            last_modified=str(getattr(item, "lastUpdated", "")) or None,
            created_at=str(getattr(item, "dateCreated", "")) or None,
            tags=[str(t) for t in (getattr(item, "tags", None) or [])],
            description=getattr(item, "subtitle", None) or getattr(item, "description", None),
            name=title,
            stars=getattr(item, "voteCount", 0) or 0,
            size_bytes=getattr(item, "totalBytes", 0) or 0,
            metadata={"backend": "kaggle-api"},
        ))
    return results
