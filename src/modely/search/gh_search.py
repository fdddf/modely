"""GitHub search backend for modely-ai."""

import json
import sys
from typing import List, Optional

import requests

from .types import SearchResult

_SEARCH_URL = "https://api.github.com/search/repositories"

# Map modely sort fields to GitHub API sort values
_SORT_MAP = {
    "downloads": "forks",
    "likes": "stars",
    "lastModified": "updated",
    "created_at": "created",
}


def search_github(
    keyword: Optional[str] = None,
    *,
    sort: str = "downloads",
    direction: str = "desc",
    limit: int = 20,
    token: Optional[str] = None,
) -> List[SearchResult]:
    """Search GitHub for repositories using the REST Search API.

    Args:
        keyword: Search query string.
        sort: Sort field — ``"downloads"`` (forks), ``"likes"`` (stars),
              ``"lastModified"`` (updated), ``"created_at"`` (created).
        direction: ``"asc"`` or ``"desc"``.
        limit: Maximum results (max 100 per page).
        token: GitHub personal access token for higher rate limits.

    Returns:
        List of ``SearchResult`` objects.
    """
    gh_sort = _SORT_MAP.get(sort, "forks")
    params = {
        "q": keyword or "machine-learning",
        "sort": gh_sort,
        "order": direction,
        "per_page": min(limit, 100),
    }
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "user-agent": "modely-ai/search",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.get(
            _SEARCH_URL,
            params=params,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        print("Warning: GitHub search timed out.", file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print("Warning: Could not connect to GitHub.", file=sys.stderr)
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Warning: GitHub search HTTP error: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print("Warning: GitHub returned invalid JSON.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: GitHub search failed: {e}", file=sys.stderr)
        return []

    items = data.get("items")
    if not isinstance(items, list):
        return []

    output = []
    for item in items:
        try:
            license_info = item.get("license") or {}
            result = SearchResult(
                id=item.get("full_name", ""),
                source="github",
                repo_type="tool",
                url=item.get("html_url", ""),
                author=(item.get("owner") or {}).get("login"),
                downloads=item.get("forks_count", 0) or 0,
                likes=item.get("stargazers_count", 0) or 0,
                last_modified=item.get("updated_at"),
                created_at=item.get("created_at"),
                pipeline_tag=item.get("language"),
                library_name=None,
                tags=item.get("topics") or [],
                license=license_info.get("spdx_id"),
                description=item.get("description"),
            )
            output.append(result)
        except Exception:
            continue

    return output
