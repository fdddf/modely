"""Catalog label and local metadata implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..audit import record_audit_event
from ..common import cache
from ..types import RepoRef
from ..uri import parse_modely_uri

METADATA_FILE = "asset_metadata.json"
_ALLOWED_STATUSES = {"candidate", "evaluating", "approved", "production", "deprecated"}


def metadata_path() -> Path:
    """Return the local resource metadata file path."""
    return Path(cache.CONFIG_DIR) / METADATA_FILE


def load_asset_metadata(*, metadata_path_func=None) -> dict:
    """Load local tags, notes, favorites, lifecycle states, and project sets."""
    path = (metadata_path_func or metadata_path)()
    if not path.exists():
        return {"resources": {}, "projects": {}}
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"resources": {}, "projects": {}}
    data.setdefault("resources", {})
    data.setdefault("projects", {})
    return data


def save_asset_metadata(data: dict, *, metadata_path_func=None) -> None:
    """Persist local resource metadata."""
    path = (metadata_path_func or metadata_path)()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def resource_key(resource: str, *, source: str = "auto", repo_type: str = "auto") -> str:
    """Normalize a resource into a metadata key."""
    ref = parse_modely_uri(resource, source=None if source == "auto" else source, repo_type=repo_type)
    return _ref_key(ref)


def get_asset_record(resource: str, *, source: str = "auto", repo_type: str = "auto", metadata_path_func=None) -> dict:
    """Return local metadata for one resource."""
    data = load_asset_metadata(metadata_path_func=metadata_path_func)
    return data["resources"].get(resource_key(resource, source=source, repo_type=repo_type), _empty_record())


def update_asset_record(
    resource: str,
    *,
    source: str = "auto",
    repo_type: str = "auto",
    add_tags: Optional[list[str]] = None,
    remove_tags: Optional[list[str]] = None,
    note: Optional[str] = None,
    favorite: Optional[bool] = None,
    status: Optional[str] = None,
    project: Optional[str] = None,
    metadata_path_func=None,
) -> dict:
    """Update local metadata for a resource and return the record."""
    data = load_asset_metadata(metadata_path_func=metadata_path_func)
    key = resource_key(resource, source=source, repo_type=repo_type)
    record = data["resources"].setdefault(key, _empty_record())
    record["tags"] = sorted((set(record.get("tags") or []) | set(add_tags or [])) - set(remove_tags or []))
    if note is not None:
        record["note"] = note
    if favorite is not None:
        record["favorite"] = favorite
    if status is not None:
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"Unsupported lifecycle status: {status}")
        record["status"] = status
    if project:
        projects = data.setdefault("projects", {})
        members = set(projects.get(project, []))
        members.add(key)
        projects[project] = sorted(members)
        record["projects"] = sorted(set(record.get("projects") or []) | {project})
    save_asset_metadata(data, metadata_path_func=metadata_path_func)
    record_audit_event("label.set", resource=key, metadata={"tags": record.get("tags"), "status": record.get("status"), "projects": record.get("projects")})
    return record


def list_asset_metadata(*, project: Optional[str] = None, favorites: bool = False, metadata_path_func=None) -> dict:
    """List resources with local metadata, optionally filtered."""
    data = load_asset_metadata(metadata_path_func=metadata_path_func)
    resources = data.get("resources") or {}
    if project:
        keys = set((data.get("projects") or {}).get(project, []))
        resources = {key: value for key, value in resources.items() if key in keys}
    if favorites:
        resources = {key: value for key, value in resources.items() if value.get("favorite")}
    return {"resources": resources, "projects": data.get("projects") or {}}


def export_project(project: str, *, metadata_path_func=None) -> dict:
    """Export one project collection as a shareable resource set."""
    data = load_asset_metadata(metadata_path_func=metadata_path_func)
    keys = (data.get("projects") or {}).get(project, [])
    resources = data.get("resources") or {}
    return {
        "project": project,
        "resources": [{"key": key, **(resources.get(key) or _empty_record())} for key in keys],
        "count": len(keys),
    }


def print_project_export(payload: dict, *, as_json: bool = False) -> None:
    """Print a project export."""
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return
    print(f"Project: {payload.get('project')}")
    print(f"Resources: {payload.get('count', 0)}")
    for item in payload.get("resources") or []:
        tags = ", ".join(item.get("tags") or []) or "-"
        print(f"  - {item.get('key')} [{item.get('status') or '-'}] tags={tags}")


def print_asset_metadata(payload: dict, *, as_json: bool = False) -> None:
    """Print local resource metadata."""
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return
    resources = payload.get("resources") or {}
    if not resources:
        print("No resource metadata saved.")
        return
    for key, record in sorted(resources.items()):
        tags = ", ".join(record.get("tags") or []) or "-"
        projects = ", ".join(record.get("projects") or []) or "-"
        fav = " ★" if record.get("favorite") else ""
        print(f"{key}{fav}")
        print(f"  Status:   {record.get('status') or '-'}")
        print(f"  Tags:     {tags}")
        print(f"  Projects: {projects}")
        if record.get("note"):
            print(f"  Note:     {record['note']}")


def _ref_key(ref: RepoRef) -> str:
    return f"{ref.source}:{ref.repo_type}:{ref.repo_id}"


def _empty_record() -> dict:
    return {"tags": [], "note": "", "favorite": False, "status": "candidate", "projects": []}


__all__ = [name for name in globals() if not name.startswith("_")]
