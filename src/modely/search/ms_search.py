"""ModelScope search backend for modely-ai."""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from .types import SearchResult


# ModelScope uses the PUT-method dolphin API for model search
_SEARCH_URL = "{endpoint}/api/v1/dolphin/models"
# ModelScope uses the GET-method OpenAPI for dataset search
_DATASET_SEARCH_URL = "{endpoint}/openapi/v1/datasets"


def _to_iso(ts) -> Optional[str]:
    """Convert a Unix timestamp (int seconds or ISO string) to ISO 8601."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, OSError):
            return None
    return str(ts)


def _build_search_body(
    keyword: Optional[str],
    task: Optional[str],
    limit: int,
    page: int = 1,
    sort: str = "downloads",
) -> Dict:
    """Build the JSON body for ModelScope dolphin search API (models only)."""
    # Note: dolphin API only accepts SortBy="Default"; other values return 400.
    # Sorting is done client-side in search_modelscope().
    body: Dict = {
        "PageSize": limit,
        "PageNumber": page,
        "Name": keyword or "",
        "tags": [],
        "tasks": [],
        "SortBy": "Default",
    }
    if task:
        body["tasks"] = [task]
    return body


def _parse_model_item(item: Dict) -> SearchResult:
    """Parse a ModelScope model item from dolphin API into a SearchResult."""
    # Build full repo ID from Path/Name
    path = item.get("Path", "")
    name = item.get("Name", "")
    if path and name:
        repo_id = f"{path}/{name}"
    else:
        repo_id = name or path or item.get("Id", "")

    # Tasks field can be a list of dicts (each with Name) or a list of strings
    tasks_raw = item.get("Tasks") or []
    if tasks_raw and isinstance(tasks_raw[0], dict):
        pipeline_tag = tasks_raw[0].get("Name")
    else:
        pipeline_tag = tasks_raw[0] if tasks_raw else None

    # Tags field can be a list of dicts or strings
    tags_raw = item.get("Tags") or []
    tags: List[str] = []
    for t in tags_raw:
        if isinstance(t, dict):
            tag_name = t.get("Name") or t.get("value")
            if tag_name:
                tags.append(str(tag_name))
        elif t:
            tags.append(str(t))

    # Likes is often null; fall back to Stars
    likes = item.get("Likes")
    if likes is None:
        likes = item.get("Stars", 0) or 0

    return SearchResult(
        id=repo_id,
        source="ms",
        repo_type="model",
        url=f"https://modelscope.cn/models/{repo_id}",
        author=item.get("Organization") or item.get("Path"),
        downloads=item.get("Downloads", 0) or 0,
        likes=likes,
        last_modified=_to_iso(item.get("LastUpdatedTime") or item.get("CreatedTime")),
        created_at=_to_iso(item.get("CreatedTime")),
        pipeline_tag=pipeline_tag,
        library_name=None,
        tags=tags,
        license=item.get("License"),
        description=item.get("Description") or item.get("ChineseName"),
    )


def _parse_dataset_item(item: Dict) -> SearchResult:
    """Parse a ModelScope dataset item from OpenAPI v1 into a SearchResult."""
    repo_id = item.get("id", "")
    tags_raw = item.get("tags") or []
    tags = [str(t) for t in tags_raw if t]

    tasks_raw = item.get("tasks") or []
    pipeline_tag = tasks_raw[0] if tasks_raw else None

    return SearchResult(
        id=repo_id,
        source="ms",
        repo_type="dataset",
        url=f"https://modelscope.cn/datasets/{repo_id}",
        author=repo_id.split("/")[0] if "/" in repo_id else None,
        downloads=item.get("downloads", 0) or 0,
        likes=item.get("likes", 0) or 0,
        last_modified=_to_iso(item.get("last_modified")),
        created_at=_to_iso(item.get("created_at")),
        pipeline_tag=pipeline_tag,
        library_name=None,
        tags=tags,
        license=item.get("license"),
        description=item.get("description") or item.get("display_name"),
    )


def _search_modelscope_models(
    keyword: Optional[str],
    task: Optional[str],
    sort: str,
    direction: str,
    limit: int,
) -> List[SearchResult]:
    """Search ModelScope models via the dolphin API."""
    endpoint = os.environ.get("MODELSCOPE_ENDPOINT", "https://www.modelscope.cn")
    url = _SEARCH_URL.format(endpoint=endpoint)
    body = _build_search_body(keyword, task, limit, sort=sort)

    try:
        response = requests.put(
            url,
            json=body,
            timeout=30,
            headers={
                "Content-Type": "application/json",
                "user-agent": "modely-ai/search",
            },
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        print("Warning: ModelScope search timed out.", file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print("Warning: Could not connect to ModelScope.", file=sys.stderr)
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Warning: ModelScope search HTTP error: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print("Warning: ModelScope returned invalid JSON.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: ModelScope search failed: {e}", file=sys.stderr)
        return []

    inner = data.get("Data")
    if not isinstance(inner, dict):
        return []
    model_data = inner.get("Model")
    if not isinstance(model_data, dict):
        return []
    items = model_data.get("Models")
    if not isinstance(items, list):
        return []

    output = []
    for item in items:
        try:
            result = _parse_model_item(item)
            output.append(result)
        except Exception:
            continue

    # Client-side sorting (dolphin API SortBy="Default" only)
    if sort == "lastModified":
        output.sort(key=lambda r: r.last_modified or "", reverse=(direction == "desc"))
    elif sort == "likes":
        output.sort(key=lambda r: r.likes, reverse=(direction == "desc"))
    elif sort == "created_at":
        output.sort(key=lambda r: r.created_at or "", reverse=(direction == "desc"))
    else:  # downloads (default)
        output.sort(key=lambda r: r.downloads, reverse=(direction == "desc"))

    return output


def _search_modelscope_datasets(
    keyword: Optional[str],
    sort: str,
    direction: str,
    limit: int,
) -> List[SearchResult]:
    """Search ModelScope datasets via the OpenAPI v1 endpoint."""
    endpoint = os.environ.get("MODELSCOPE_ENDPOINT", "https://www.modelscope.cn")
    url = _DATASET_SEARCH_URL.format(endpoint=endpoint)

    # Map sort fields to OpenAPI sort values
    sort_map = {
        "downloads": "downloads",
        "lastModified": "last_modified",
        "likes": "likes",
        "created_at": "created_at",
    }

    params: Dict = {
        "page_number": 1,
        "page_size": limit,
        "sort": sort_map.get(sort, "downloads"),
    }
    if keyword:
        params["search"] = keyword

    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
            headers={"user-agent": "modely-ai/search"},
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        print("Warning: ModelScope dataset search timed out.", file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print("Warning: Could not connect to ModelScope.", file=sys.stderr)
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Warning: ModelScope dataset search HTTP error: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print("Warning: ModelScope returned invalid JSON.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: ModelScope dataset search failed: {e}", file=sys.stderr)
        return []

    datasets = data.get("data", {}).get("datasets", [])
    if not isinstance(datasets, list):
        return []

    output = []
    for item in datasets:
        try:
            result = _parse_dataset_item(item)
            output.append(result)
        except Exception:
            continue

    # Client-side sort — OpenAPI supports sort, but we sort again for direction consistency
    if direction == "asc":
        if sort == "lastModified":
            output.sort(key=lambda r: r.last_modified or "")
        elif sort == "likes":
            output.sort(key=lambda r: r.likes)
        elif sort == "created_at":
            output.sort(key=lambda r: r.created_at or "")
        else:
            output.sort(key=lambda r: r.downloads)
    # desc is the default from the API, but we ensure it
    if direction == "desc":
        if sort == "lastModified":
            output.sort(key=lambda r: r.last_modified or "", reverse=True)
        elif sort == "likes":
            output.sort(key=lambda r: r.likes, reverse=True)
        elif sort == "created_at":
            output.sort(key=lambda r: r.created_at or "", reverse=True)
        else:
            output.sort(key=lambda r: r.downloads, reverse=True)

    return output


def search_modelscope(
    keyword: Optional[str] = None,
    *,
    repo_type: str = "model",
    task: Optional[str] = None,
    sort: str = "downloads",
    direction: str = "desc",
    limit: int = 20,
) -> List[SearchResult]:
    """Search ModelScope for models or datasets.

    Models use the PUT-method dolphin API. Datasets use the
    GET-method OpenAPI v1 endpoint.
    """
    if repo_type == "dataset":
        return _search_modelscope_datasets(keyword, sort, direction, limit)

    return _search_modelscope_models(keyword, task, sort, direction, limit)
