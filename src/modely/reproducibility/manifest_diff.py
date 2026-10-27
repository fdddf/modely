"""Manifest diff helpers."""

from __future__ import annotations

from .lockfiles import read_manifest


def diff_manifests(left, right) -> dict:
    """Return added, removed, and changed files between two manifest objects."""
    left_files = {f.path: f for f in left.files}
    right_files = {f.path: f for f in right.files}
    added = sorted(set(right_files) - set(left_files))
    removed = sorted(set(left_files) - set(right_files))
    changed = []
    for path in sorted(set(left_files) & set(right_files)):
        before = left_files[path]
        after = right_files[path]
        if (before.size or 0) != (after.size or 0) or (before.sha256 and after.sha256 and before.sha256 != after.sha256):
            changed.append({"path": path, "left": before.to_dict(), "right": after.to_dict()})
    return {
        "added": [right_files[p].to_dict() for p in added],
        "removed": [left_files[p].to_dict() for p in removed],
        "changed": changed,
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed)},
    }


def diff_manifest_files(left_path: str, right_path: str) -> dict:
    """Read and diff two manifest files."""
    return diff_manifests(read_manifest(left_path), read_manifest(right_path))


def diff_manifest_dicts(left_dict: dict, right_dict: dict) -> dict:
    """Diff two manifests given as dicts (used by API route with inline content)."""
    from ..types import DownloadManifest, FileInfo

    def _files_from_dict(data: dict):
        return [FileInfo(**item) for item in data.get("files", [])]

    left = DownloadManifest(
        source=left_dict.get("source", ""), repo_type=left_dict.get("repo_type", ""),
        repo_id=left_dict.get("repo_id", ""), revision=left_dict.get("revision"),
        files=_files_from_dict(left_dict),
    )
    right = DownloadManifest(
        source=right_dict.get("source", ""), repo_type=right_dict.get("repo_type", ""),
        repo_id=right_dict.get("repo_id", ""), revision=right_dict.get("revision"),
        files=_files_from_dict(right_dict),
    )
    return diff_manifests(left, right)


def diff_asset_versions(left_version_id: str, right_version_id: str, *, repository) -> dict:
    """Compare two asset versions using the Phase 1 repository.

    Returns file-level diff plus metadata/license/risk/policy deltas.
    """

    left_version = repository.versions.get_version(left_version_id)
    right_version = repository.versions.get_version(right_version_id)

    if not left_version:
        raise KeyError(f"Version not found: {left_version_id}")
    if not right_version:
        raise KeyError(f"Version not found: {right_version_id}")

    left_asset = repository.assets.get_asset(left_version.asset_id)
    right_asset = repository.assets.get_asset(right_version.asset_id)

    # Compare file lists from versions
    left_files_list = list(repository.files.list_files(left_version.asset_id, left_version.id))
    right_files_list = list(repository.files.list_files(right_version.asset_id, right_version.id))

    left_files = {f.path: f for f in left_files_list}
    right_files = {f.path: f for f in right_files_list}

    added_paths = sorted(set(right_files) - set(left_files))
    removed_paths = sorted(set(left_files) - set(right_files))
    common = sorted(set(left_files) & set(right_files))

    changed = []
    for path in common:
        lf, rf = left_files[path], right_files[path]
        if lf.size != rf.size or (lf.sha256 and rf.sha256 and lf.sha256 != rf.sha256):
            changed.append({
                "path": path,
                "left": lf.to_dict() if hasattr(lf, "to_dict") else dict(lf),
                "right": rf.to_dict() if hasattr(rf, "to_dict") else dict(rf),
            })

    result = {
        "added_files": [right_files[p].to_dict() if hasattr(right_files[p], "to_dict") else dict(right_files[p]) for p in added_paths],
        "removed_files": [left_files[p].to_dict() if hasattr(left_files[p], "to_dict") else dict(left_files[p]) for p in removed_paths],
        "changed_files": changed,
        "added": added_paths,
        "removed": removed_paths,
        "changed": changed,
        "summary": {"added": len(added_paths), "removed": len(removed_paths), "changed": len(changed)},
    }

    # Metadata deltas
    result["metadata_delta"] = _diff_dicts(
        left_version.metadata if hasattr(left_version, "metadata") else {},
        right_version.metadata if hasattr(right_version, "metadata") else {},
    )

    # License delta
    left_license = (left_asset.license if hasattr(left_asset, "license") else None) or ""
    right_license = (right_asset.license if hasattr(right_asset, "license") else None) or ""
    if left_license != right_license:
        result["license_delta"] = {"left": left_license, "right": right_license, "changed": True}
    else:
        result["license_delta"] = {"left": left_license, "right": right_license, "changed": False}

    # Risk/policy delta (from version metadata)
    left_risk = (left_version.metadata.get("risk_level") if hasattr(left_version, "metadata") and left_version.metadata else "unknown")
    right_risk = (right_version.metadata.get("risk_level") if hasattr(right_version, "metadata") and right_version.metadata else "unknown")
    result["risk_delta"] = {"left": left_risk, "right": right_risk, "changed": left_risk != right_risk}

    left_policy = (left_asset.metadata.get("policy_status") if hasattr(left_asset, "metadata") else None) or "not_evaluated"
    right_policy = (right_asset.metadata.get("policy_status") if hasattr(right_asset, "metadata") else None) or "not_evaluated"
    result["policy_delta"] = {"left": left_policy, "right": right_policy, "changed": left_policy != right_policy}

    # Model card delta (from asset tags + metadata)
    left_card = sorted(left_asset.tags if hasattr(left_asset, "tags") else [])
    right_card = sorted(right_asset.tags if hasattr(right_asset, "tags") else [])
    result["model_card_delta"] = {"left": left_card, "right": right_card, "changed": left_card != right_card}

    return result


def _diff_dicts(left: dict, right: dict) -> dict:
    """Compute added, removed, and changed keys between two dicts."""
    left_keys = set(left)
    right_keys = set(right)
    added_keys = right_keys - left_keys
    removed_keys = left_keys - right_keys
    common = left_keys & right_keys
    changed_keys = {k: {"left": left[k], "right": right[k]} for k in common if left[k] != right[k]}
    return {
        "added": {k: right[k] for k in added_keys},
        "removed": {k: left[k] for k in removed_keys},
        "changed": changed_keys,
        "changed_count": len(added_keys) + len(removed_keys) + len(changed_keys),
    }


__all__ = [
    "diff_asset_versions",
    "diff_manifest_dicts",
    "diff_manifest_files",
    "diff_manifests",
]
