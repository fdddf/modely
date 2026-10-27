"""Watch route adapters — expose watch target listing and drift checking as REST endpoints."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schemas.envelopes import error_response, success_response


WATCH_HISTORY_FILE = os.path.join(str(Path.home()), ".modely", "watch_history.json")
DISCOVER_DESCRIPTION_LIMIT = 240
DISCOVER_TEXT_LIMIT = 160
DISCOVER_TAG_LIMIT = 12


def _extract(payload: dict, key: str) -> str:
    """Get a string value from *payload*, also checking nested body dict."""
    val = payload.get(key, "")
    if not val and "payload" in payload:
        inner = payload.get("payload", {})
        if isinstance(inner, dict):
            val = inner.get(key, "")
    return str(val).strip()


def _as_text(value: Any, *, limit: int = DISCOVER_TEXT_LIMIT) -> str | None:
    """Convert search backend values to compact UI-safe text."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    elif isinstance(value, dict):
        text = ""
        for key in ("login", "name", "Name", "FullName", "Path", "id", "Id"):
            inner = value.get(key)
            if inner:
                text = str(inner)
                break
        if not text:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)

    text = " ".join(text.split())
    if not text:
        return None
    if len(text) > limit:
        return text[: max(limit - 3, 0)].rstrip() + "..."
    return text


def _as_int(value: Any) -> int:
    """Best-effort integer conversion for remote search counters."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_tags(value: Any) -> list[str]:
    """Return a small tag list for the Discover table payload."""
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for tag in value:
        text = _as_text(tag, limit=80)
        if text:
            tags.append(text)
        if len(tags) >= DISCOVER_TAG_LIMIT:
            break
    return tags


def _discover_result_payload(result: Any) -> dict[str, Any]:
    """Serialize a remote search result into the compact web Discover schema."""
    data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    rid = _as_text(data.get("id"), limit=300) or _as_text(data.get("name"), limit=300) or ""
    name = _as_text(data.get("name"), limit=180)
    description = _as_text(
        data.get("description") or data.get("summary"),
        limit=DISCOVER_DESCRIPTION_LIMIT,
    )

    return {
        "id": rid,
        "source": _as_text(data.get("source"), limit=32) or "",
        "repo_type": _as_text(data.get("repo_type"), limit=32) or "",
        "url": _as_text(data.get("url"), limit=500) or "",
        "author": _as_text(data.get("author"), limit=120),
        "downloads": _as_int(data.get("downloads")),
        "likes": _as_int(data.get("likes")),
        "stars": _as_int(data.get("stars")),
        "forks": _as_int(data.get("forks")),
        "last_modified": _as_text(data.get("last_modified"), limit=64),
        "created_at": _as_text(data.get("created_at"), limit=64),
        "pipeline_tag": _as_text(data.get("pipeline_tag"), limit=80),
        "library_name": _as_text(data.get("library_name"), limit=80),
        "tags": _as_tags(data.get("tags")),
        "license": _as_text(data.get("license"), limit=80),
        "description": description,
        "name": name or (rid.rsplit("/", 1)[-1] if rid else None),
        "modely_uri": _as_text(data.get("modely_uri"), limit=500),
        "size_bytes": _as_int(data.get("size_bytes")),
    }


def list_watch_targets(config_path: str | None = None, *, config: str | None = None, request_id: str = "req_unknown", **kwargs) -> dict:
    """Return all configured watch targets with their current state.

    Query params:
      - config: optional path to watch config JSON (default ~/.modely/watch.json)

    Drift status is derived from the stored state file (from a previous drift check
    or watch run).  A separate ``POST /api/v1/watch/check`` call is needed to get
    live drift status.
    """
    from modely.syncing.watch import list_targets as _list_targets

    # Accept both ``config`` (query param convention) and ``config_path``
    cfg = config or config_path

    try:
        rows = _list_targets(cfg or None)
    except FileNotFoundError as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    targets = []
    for row in rows:
        target = row["target"]
        state = row.get("state", {})
        # Derive drift status from stored state fingerprint
        fingerprint = state.get("fingerprint")
        drift_status: str = "idle"
        if state.get("error"):
            drift_status = "error"
        elif fingerprint:
            drift_status = "unchanged"  # last known state was synced

        targets.append({
            "key": row["key"],
            "source": target.get("source", ""),
            "repo_type": target.get("repo_type", ""),
            "repo_id": target.get("repo_id", ""),
            "revision": target.get("revision", ""),
            "download_mode": target.get("download", "snapshot"),
            "allow_patterns": target.get("allow_patterns", []) or [],
            "ignore_patterns": target.get("ignore_patterns", []) or [],
            "last_checked_at": state.get("last_checked_at"),
            "last_downloaded_at": state.get("last_downloaded_at"),
            "last_download_path": state.get("last_download_path"),
            "fingerprint": fingerprint,
            "error": state.get("error"),
            # Drift fields derived from stored state
            "drift_status": drift_status,
            "drifted": drift_status == "drifted",
            "previous_fingerprint": None,  # not available from stored state
            "current_fingerprint": fingerprint,
        })


    return success_response({"targets": targets, "total": len(targets)}, request_id=request_id)


def check_drift(config_path: str | None = None, *, config: str | None = None, request_id: str = "req_unknown", **kwargs) -> dict:
    """Check all configured watch targets for remote drift WITHOUT downloading.

    Returns the current fingerprint vs last-known fingerprint for each target.
    Calls ``modely.syncing.watch.check_drift`` internally.
    """
    from modely.syncing.watch import check_drift as _check_drift

    cfg = config or config_path
    try:
        results = _check_drift(cfg or None)
    except FileNotFoundError as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    items = []
    for result in results:
        target = result.get("target", {})
        items.append({
            "key": result["key"],
            "source": target.get("source", ""),
            "repo_type": target.get("repo_type", ""),
            "repo_id": target.get("repo_id", ""),
            "revision": target.get("revision", ""),
            "status": result["status"],
            "previous_fingerprint": result.get("previous"),
            "current_fingerprint": result.get("current"),
            "error": result.get("error"),
        })

    drifted = sum(1 for item in items if item["status"] == "drifted")
    errors = sum(1 for item in items if item["status"] == "error")
    return success_response({
        "results": items,
        "total": len(items),
        "drifted": drifted,
        "errors": errors,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }, request_id=request_id)


def get_watch_history(
    config_path: str | None = None,
    *,
    config: str | None = None,
    request_id: str = "req_unknown",
    **kwargs,
) -> dict:
    """Return change history for watch targets.

    Query params:
      - config: optional path to watch config JSON
      - target_key: optional filter to a specific target key (source:type:repo_id:revision)

    History is read from ``~/.modely/watch_history.json``.
    """
    history_path = WATCH_HISTORY_FILE
    if not os.path.exists(history_path):
        return success_response({"events": [], "total": 0}, request_id=request_id)

    try:
        with open(history_path, "r") as f:
            events = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return error_response("internal_error", f"Failed to read watch history: {exc}", request_id=request_id)

    target_filter = (kwargs.get("target_key") or "").strip()
    if target_filter:
        events = [e for e in events if e.get("key") == target_filter]

    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return success_response({"events": events, "total": len(events)}, request_id=request_id)


def remote_search_route(*, request_id: str = "req_unknown", **query_params) -> dict:
    """Search remote HF / ModelScope / GitHub repositories for discovery.

    Query params:
      - q: keyword (required)
      - source: hf | ms | github | all (default all)
      - repo_type: model | dataset | tool | all (default all)
      - page: page number (1-based, default 1)
      - page_size: results per page (10 | 20 | 30, default 20)

    Searches with a larger internal limit per source, then paginates from the
    deduplicated result set.  The ``page`` parameter is clamped to the last
    10 pages so callers cannot walk arbitrarily far back.
    """
    from modely.search import search as _remote_search
    from modely.search.gh_search import search_github

    q = str(query_params.get("q", "")).strip()
    if not q:
        return error_response("validation_error", "Query parameter 'q' is required", request_id=request_id)

    source = str(query_params.get("source", "all")).strip() or "all"
    repo_type = str(query_params.get("repo_type", "all")).strip() or "all"

    # Page size
    try:
        page_size = int(query_params.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20
    if page_size not in (10, 20, 30):
        page_size = 20

    # Internal fetch limit: enough to fill at most 10 pages
    MAX_PAGES = 10
    internal_limit = page_size * MAX_PAGES
    # Cap per-source limit at 50 (what backends support)
    per_source_limit = min(internal_limit, 50)

    # Page
    try:
        page = int(query_params.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    results: list = []

    # Map UI-level "all"/"tool" to what the search backends understand
    search_repo_types: list = []
    if repo_type in ("all", "model"):
        search_repo_types.append("model")
    if repo_type in ("all", "dataset"):
        search_repo_types.append("dataset")

    try:
        for rt in search_repo_types:
            try:
                batch = _remote_search(keyword=q, source=source, repo_type=rt, limit=per_source_limit)
                results.extend(batch)
            except Exception:
                pass  # a source may not support a repo_type; skip gracefully

        # GitHub "tool" type — use gh_search directly
        if repo_type in ("all", "tool") and source in ("all", "github"):
            try:
                gh_results = search_github(keyword=q, sort="stars", limit=per_source_limit)
                results.extend(gh_results)
            except Exception:
                pass
    except Exception as exc:
        return error_response("search_error", f"Remote search failed: {exc}", request_id=request_id)

    # Dedupe by id
    seen: set = set()
    deduped = []
    for r in results:
        d = _discover_result_payload(r)
        rid = d.get("id", "")
        if rid and rid not in seen:
            seen.add(rid)
            deduped.append(d)

    total = len(deduped)
    total_pages = max(1, (total + page_size - 1) // page_size)
    # Clamp page to within available pages (max MAX_PAGES conceptual window)
    page = min(page, total_pages)

    # Slice for the requested page
    start = (page - 1) * page_size
    end = start + page_size
    page_results = deduped[start:end]

    return success_response({
        "results": page_results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }, request_id=request_id)


def add_watch_target(config: str = "", *, request_id: str = "req_unknown", **payload) -> dict:
    """Add a new target to the watch config.

    Body: { config: "...", target: { source, repo_type, repo_id, revision?, ... } }
    """
    from modely.syncing.watch import add_target as _add_target

    cfg = _extract(payload, "config") or config
    target_raw = payload.get("target")
    if target_raw is None and "payload" in payload:
        inner = payload.get("payload", {})
        if isinstance(inner, dict):
            target_raw = inner.get("target")

    if not isinstance(target_raw, dict):
        return error_response("validation_error", "Missing required field: target", request_id=request_id, details={"field": "target"})

    try:
        result = _add_target(cfg or None, target_raw)
    except FileNotFoundError as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    return success_response(result, request_id=request_id)


def remove_watch_target(config: str = "", *, request_id: str = "req_unknown", **payload) -> dict:
    """Remove a target from the watch config by key.

    Body: { config: "...", target_key: "source:type:repo_id:revision" }
    """
    from modely.syncing.watch import remove_target as _remove_target

    cfg = _extract(payload, "config") or config
    target_key = _extract(payload, "target_key")

    if not target_key:
        return error_response("validation_error", "Missing required field: target_key", request_id=request_id, details={"field": "target_key"})

    try:
        removed = _remove_target(cfg or None, target_key)
    except FileNotFoundError as exc:
        return error_response("not_found", str(exc), request_id=request_id)
    except ValueError as exc:
        return error_response("validation_error", str(exc), request_id=request_id)

    return success_response({"removed": removed}, request_id=request_id)


__all__ = [
    "add_watch_target",
    "check_drift",
    "get_watch_history",
    "list_watch_targets",
    "remote_search_route",
    "remove_watch_target",
]
