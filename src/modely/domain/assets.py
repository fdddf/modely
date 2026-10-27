"""Asset domain objects for the enterprise catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..types import CatalogEntry, CatalogReport, FileInfo, RepoInfo
from .policies import OPERATIONAL_STATES, VISIBILITY_LEVELS

RESOURCE_TYPES: tuple[str, ...] = ("model", "dataset", "tool", "space", "notebook", "competition")


@dataclass
class AssetIdentity:
    """Stable source identity for an enterprise catalog asset."""

    source: str
    repo_type: str
    namespace: str | None = None
    name: str | None = None
    repo_id: str | None = None
    revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Asset:
    """Minimal enterprise catalog asset DTO.

    This intentionally stays small and compatible with the existing catalog/report
    dataclasses while Phase 1 solidifies repository boundaries.
    """

    id: str
    identity: AssetIdentity
    source_url: str = ""
    license: str | None = None
    tags: list[str] = field(default_factory=list)
    size: int = 0
    file_count: int = 0
    checksum: str | None = None
    operational_state: str = "discovered"
    visibility: str = "organization"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.identity.repo_type not in RESOURCE_TYPES:
            raise ValueError(f"Unsupported resource type: {self.identity.repo_type}")
        if self.operational_state not in OPERATIONAL_STATES:
            raise ValueError(f"Unsupported operational state: {self.operational_state}")
        if self.visibility not in VISIBILITY_LEVELS:
            raise ValueError(f"Unsupported visibility: {self.visibility}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "RESOURCE_TYPES",
    "Asset",
    "AssetIdentity",
    "CatalogEntry",
    "CatalogReport",
    "FileInfo",
    "RepoInfo",
]
