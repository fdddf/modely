"""Asset version domain objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AssetVersionIdentity:
    """Stable source identity for a mirrored asset version."""

    asset_id: str
    version: str | None = None
    revision: str | None = None
    source: str | None = None
    repo_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetVersion:
    """Version-level metadata recorded by the local mirror catalog."""

    id: str
    asset_id: str
    identity: AssetVersionIdentity
    revision: str | None = None
    created_at: str | None = None
    discovered_at: str | None = None
    size: int = 0
    file_count: int = 0
    checksum: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "AssetVersion",
    "AssetVersionIdentity",
]
