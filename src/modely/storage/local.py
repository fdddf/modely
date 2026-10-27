"""Local filesystem storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterable

from .base import StorageCapabilities, StoredObject
from .checksums import sha256_file


class LocalStorageBackend:
    """Simple local directory storage backend for single-node mirrors."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _normalize_key(self, key: str, *, allow_empty: bool = False) -> str:
        normalized = PurePosixPath(key.replace("\\", "/").lstrip("/"))
        if normalized.is_absolute() or any(part == ".." for part in normalized.parts):
            raise ValueError(f"Unsafe storage key: {key}")
        value = normalized.as_posix()
        if value in {"", "."}:
            if allow_empty:
                return ""
            raise ValueError("Storage key must not be empty")
        return value

    def _path(self, key: str, *, allow_empty: bool = False) -> Path:
        normalized = self._normalize_key(key, allow_empty=allow_empty)
        path = (self.root / normalized).resolve() if normalized else self.root
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Unsafe storage key: {key}") from exc
        return path

    def put_file(self, key: str, path: str | Path, *, metadata: dict | None = None) -> StoredObject:
        normalized = self._normalize_key(key)
        target = self._path(normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        return StoredObject(
            key=normalized,
            size=target.stat().st_size,
            sha256=sha256_file(str(target)),
            uri=str(target),
            metadata=metadata or {},
        )

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def get(self, key: str) -> bytes:
        with self.open(key) as handle:
            return handle.read()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def checksum(self, key: str) -> str:
        return sha256_file(str(self._path(key)))

    def list(self, prefix: str = "") -> Iterable[StoredObject]:
        normalized_prefix = self._normalize_key(prefix, allow_empty=True)
        root = self._path(normalized_prefix, allow_empty=True)
        candidates = root.rglob("*") if root.exists() and root.is_dir() else self.root.rglob("*")
        for path in candidates:
            if path.is_file():
                path = path.resolve()
                try:
                    key = path.relative_to(self.root).as_posix()
                except ValueError:
                    continue
                if key.startswith(normalized_prefix):
                    yield StoredObject(key=key, size=path.stat().st_size, sha256=sha256_file(str(path)), uri=str(path))

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(backend="local", local_disk=True, checksum=True, atomic_write=False)


__all__ = ["LocalStorageBackend"]
