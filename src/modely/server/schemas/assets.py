"""Asset API schemas for the Phase 1b enterprise API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AssetResponse:
    """Stable response shape for catalog asset list and detail APIs."""

    id: str
    source: str
    repo_type: str
    repo_id: str
    revision: str | None = None
    license: str | None = None
    tags: list[str] = field(default_factory=list)
    size: int = 0
    file_count: int = 0
    checksum: str | None = None
    operational_state: str = "discovered"
    visibility: str = "organization"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetListResponse:
    """Container shape used internally before envelope wrapping."""

    assets: list[AssetResponse] = field(default_factory=list)
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["total"] = self.total or len(self.assets)
        return payload


@dataclass
class AssetFileResponse:
    """Response shape for asset file listing."""

    path: str
    size: int
    sha256: str | None = None
    file_type: str = "blob"
    mime_type: str | None = None
    mtime: str | None = None
    storage_key: str | None = None
    manifest_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetDownloadUrlResponse:
    """Diagnostic download URL metadata — NOT production download authorization."""

    asset_id: str
    download_mode: str  # local_reference, server_proxy_planned, signed_url_planned
    url_ref: str  # redacted or local file:// reference
    manifest_ref: str | None = None
    checksum_ref: str | None = None
    expires_at: str | None = None
    security_warning: str = "Phase 1 diagnostic mode: production download authorization is deferred to later phases."
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanSummaryResponse:
    """Baseline scan summary for asset detail enrichment."""

    asset_id: str
    scan_status: str = "not_evaluated"  # queued, scanning, scanned, failed, not_evaluated
    finding_count: int = 0
    secret_count: int = 0
    remote_code_detected: bool = False
    severity_summary: dict[str, int] = field(default_factory=dict)  # e.g. {"high": 1, "medium": 3}
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "AssetDownloadUrlResponse",
    "AssetFileResponse",
    "AssetListResponse",
    "AssetResponse",
    "ScanSummaryResponse",
]
