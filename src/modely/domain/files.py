"""Asset file domain objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ASSET_FILE_TYPES: tuple[str, ...] = ("blob", "lfs", "directory", "symlink", "unknown")


@dataclass
class AssetFileIdentity:
    """Stable identity for a file that belongs to a mirrored asset version."""

    asset_id: str
    path: str
    version_id: str | None = None
    revision: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetFile:
    """File-level metadata recorded by the local mirror catalog."""

    id: str
    identity: AssetFileIdentity
    path: str
    size: int = 0
    sha256: str | None = None
    etag: str | None = None
    mime_type: str | None = None
    file_type: str = "blob"
    local_path: str | None = None
    download_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.file_type not in ASSET_FILE_TYPES:
            raise ValueError(f"Unsupported asset file type: {self.file_type}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_asset_file_type(value: str) -> bool:
    return value in ASSET_FILE_TYPES


__all__ = [
    "ASSET_FILE_TYPES",
    "AssetFile",
    "AssetFileIdentity",
    "is_asset_file_type",
]
