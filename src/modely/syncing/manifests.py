"""Sync manifest generation helpers."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from ..application.file_queries import filter_files
from ..storage.base import StoredObject
from ..storage.checksums import sha256_file
from ..types import DownloadManifest, FileInfo
from ..uri import parse_modely_uri


def create_local_manifest(
    resource: str,
    local_path: str | Path,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    checksum: bool = False,
    output: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> DownloadManifest:
    """Create a deterministic manifest for files present under a local path."""
    root = Path(local_path)
    files: list[FileInfo] = []
    if root.is_file():
        files.append(
            FileInfo(
                path=_safe_manifest_path(root.name),
                size=root.stat().st_size,
                sha256=sha256_file(str(root)) if checksum else None,
            )
        )
    elif root.exists():
        for path in root.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            rel = _safe_manifest_path(path.relative_to(root).as_posix())
            files.append(FileInfo(path=rel, size=path.stat().st_size, sha256=sha256_file(str(path)) if checksum else None))
    return _build_manifest(
        resource,
        files,
        local_path=str(local_path),
        include=include,
        exclude=exclude,
        output=output,
        metadata=metadata,
        generation_source="local_path",
    )


def create_file_list_manifest(
    resource: str,
    files: Iterable[FileInfo | StoredObject | dict[str, Any]],
    *,
    local_path: str | Path | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    output: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> DownloadManifest:
    """Create a manifest from already-listed file metadata."""
    normalized = [_coerce_file_info(item) for item in files]
    return _build_manifest(
        resource,
        normalized,
        local_path=str(local_path) if local_path is not None else None,
        include=include,
        exclude=exclude,
        output=output,
        metadata=metadata,
        generation_source="file_list",
    )


def create_storage_manifest(
    resource: str,
    objects: Iterable[StoredObject],
    *,
    storage_root: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    output: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> DownloadManifest:
    """Create a manifest from objects listed by a storage backend."""
    manifest_metadata = dict(metadata or {})
    if storage_root is not None:
        manifest_metadata.setdefault("storage_root", storage_root)
    manifest = create_file_list_manifest(
        resource,
        objects,
        local_path=storage_root,
        include=include,
        exclude=exclude,
        output=None,
        metadata=manifest_metadata,
    )
    manifest.metadata["generation_source"] = "storage_objects"
    if output:
        _write_manifest(manifest, output)
    return manifest


def _build_manifest(
    resource: str,
    files: Iterable[FileInfo],
    *,
    local_path: str | None,
    include: list[str] | None,
    exclude: list[str] | None,
    output: str | Path | None,
    metadata: dict[str, Any] | None,
    generation_source: str,
) -> DownloadManifest:
    ref = parse_modely_uri(resource)
    safe_files = [_safe_file_info(file_info) for file_info in files]
    filtered = sorted(filter_files(safe_files, include, exclude), key=lambda file_info: file_info.path)
    summary = _manifest_summary(filtered)
    manifest_metadata = {
        "kind": "manifest",
        "schema_version": 2,
        "generation_source": generation_source,
        **summary,
    }
    manifest_metadata.update(metadata or {})
    manifest = DownloadManifest(
        ref.source,
        ref.repo_type,
        ref.repo_id,
        ref.revision,
        local_path,
        filtered,
        include,
        exclude,
        metadata=manifest_metadata,
    )
    if output:
        _write_manifest(manifest, output)
    return manifest


def _coerce_file_info(item: FileInfo | StoredObject | dict[str, Any]) -> FileInfo:
    if isinstance(item, FileInfo):
        return _safe_file_info(item)
    if isinstance(item, StoredObject):
        metadata = dict(item.metadata or {})
        if item.uri:
            metadata.setdefault("storage_uri", item.uri)
        return FileInfo(
            path=_safe_manifest_path(item.key),
            size=item.size,
            sha256=item.sha256,
            download_url=item.uri,
            metadata=metadata,
        )
    data = dict(item)
    allowed = {"path", "size", "type", "sha256", "download_url", "metadata"}
    return _safe_file_info(FileInfo(**{key: value for key, value in data.items() if key in allowed}))


def _safe_file_info(file_info: FileInfo) -> FileInfo:
    return FileInfo(
        path=_safe_manifest_path(file_info.path),
        size=file_info.size,
        type=file_info.type,
        sha256=file_info.sha256,
        download_url=file_info.download_url,
        metadata=dict(file_info.metadata or {}),
    )


def _safe_manifest_path(path: str) -> str:
    raw = str(path).replace("\\", "/")
    if raw.startswith("/"):
        raise ValueError(f"Unsafe manifest path: {path}")
    normalized = PurePosixPath(raw)
    if normalized.is_absolute() or any(part == ".." for part in normalized.parts):
        raise ValueError(f"Unsafe manifest path: {path}")
    value = normalized.as_posix()
    if value in {"", "."}:
        raise ValueError("Manifest path must not be empty")
    return value


def _manifest_summary(files: list[FileInfo]) -> dict[str, Any]:
    checksum_count = sum(1 for file_info in files if file_info.sha256)
    file_count = len(files)
    return {
        "file_count": file_count,
        "total_size": sum(file_info.size or 0 for file_info in files),
        "checksum_count": checksum_count,
        "missing_checksum_count": file_count - checksum_count,
        "checksum_coverage": (checksum_count / file_count) if file_count else 1.0,
    }


def _write_manifest(manifest: DownloadManifest, output: str | Path) -> None:
    with Path(output).open("w") as handle:
        json.dump(manifest.to_dict(), handle, indent=2, ensure_ascii=False, sort_keys=True)


__all__ = [
    "create_file_list_manifest",
    "create_local_manifest",
    "create_storage_manifest",
]
