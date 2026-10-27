"""Storage backend contracts for enterprise mirror storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterable, Protocol


@dataclass
class StoredObject:
    """Metadata for an object stored in an enterprise mirror backend."""

    key: str
    size: int = 0
    sha256: str | None = None
    uri: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StorageCapabilities:
    """Phase 1a storage capability flags for a backend implementation."""

    backend: str
    local_disk: bool = False
    checksum: bool = False
    atomic_write: bool = False
    range_read: bool = False
    signed_url: bool = False
    quota: bool = False
    object_storage: bool = False


class StorageBackend(Protocol):
    """Minimal storage backend protocol used by future server and worker code."""

    def put_file(self, key: str, path: str | Path, *, metadata: dict | None = None) -> StoredObject: ...
    def open(self, key: str) -> BinaryIO: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def checksum(self, key: str) -> str: ...
    def list(self, prefix: str = "") -> Iterable[StoredObject]: ...
    def delete(self, key: str) -> None: ...
    def capabilities(self) -> StorageCapabilities: ...


__all__ = ["StorageCapabilities", "StoredObject", "StorageBackend"]
