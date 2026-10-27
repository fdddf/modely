"""Resource revision diff implementation."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from ..application.file_queries import format_file_size, list_repo_files
from ..uri import parse_modely_uri


def diff_resource_revisions(resource: str, *, left_revision: str, right_revision: str, token=None, endpoint=None, source: str = "auto", repo_type: str = "auto", list_repo_files_func=None) -> dict:
    """Compare file lists between two revisions of a resource."""
    if list_repo_files_func is None:
        list_repo_files_func = list_repo_files
    ref = parse_modely_uri(resource, source=None if source == "auto" else source, repo_type=repo_type)
    with ThreadPoolExecutor(max_workers=2) as executor:
        left_future = executor.submit(list_repo_files_func, ref, revision=left_revision, token=token, endpoint=endpoint)
        right_future = executor.submit(list_repo_files_func, ref, revision=right_revision, token=token, endpoint=endpoint)
        left_files = left_future.result()
        right_files = right_future.result()
    left = {f.path: f for f in left_files if getattr(f, "type", "blob") != "tree"}
    right = {f.path: f for f in right_files if getattr(f, "type", "blob") != "tree"}
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    common = sorted(set(left) & set(right))
    changed = [path for path in common if (left[path].size or 0) != (right[path].size or 0) or (left[path].sha256 and right[path].sha256 and left[path].sha256 != right[path].sha256)]
    return {
        "resource": resource,
        "source": ref.source,
        "repo_type": ref.repo_type,
        "repo_id": ref.repo_id,
        "left_revision": left_revision,
        "right_revision": right_revision,
        "added": [_file_item(right[path]) for path in added],
        "removed": [_file_item(left[path]) for path in removed],
        "changed": [{"path": path, "left": _file_item(left[path]), "right": _file_item(right[path])} for path in changed],
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed), "common": len(common)},
    }


def print_revision_diff(diff: dict, *, as_json: bool = False) -> None:
    """Print a resource revision diff."""
    if as_json:
        print(json.dumps(diff, indent=2, ensure_ascii=False))
        return
    print(f"Resource: {diff.get('repo_id')} [{diff.get('source')}:{diff.get('repo_type')}]")
    print(f"Revisions: {diff.get('left_revision')} -> {diff.get('right_revision')}")
    summary = diff.get("summary") or {}
    print(f"Added:   {summary.get('added', 0)}")
    print(f"Removed: {summary.get('removed', 0)}")
    print(f"Changed: {summary.get('changed', 0)}")
    for section in ("added", "removed"):
        if diff.get(section):
            print(section.title() + ":")
            for item in diff[section][:20]:
                print(f"  - {item['path']} ({item['size_str']})")
    if diff.get("changed"):
        print("Changed:")
        for item in diff["changed"][:20]:
            print(f"  - {item['path']}: {item['left']['size_str']} -> {item['right']['size_str']}")


def _file_item(file_info) -> dict:
    size = file_info.size or 0
    return {"path": file_info.path, "size": size, "size_str": format_file_size(size), "sha256": file_info.sha256}


__all__ = [name for name in globals() if not name.startswith("_")]
