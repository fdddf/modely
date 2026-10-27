"""Catalog repository contracts for enterprise local mirror metadata."""

from __future__ import annotations

from typing import Any, Iterable, Protocol

from ..domain.assets import Asset, AssetIdentity
from ..domain.files import AssetFile, AssetFileIdentity
from ..domain.snapshots import (
    ApprovedSnapshot,
    SnapshotChannel,
    SnapshotPromotion,
    SnapshotRollback,
    SnapshotRepository,
)
from ..domain.versions import AssetVersion, AssetVersionIdentity
from ..syncing.jobs import SyncJob
from ..domain.sync_jobs import SyncJobIdentity


class AssetRepository(Protocol):
    """Backend-neutral repository contract for catalog assets."""

    def get_asset(self, asset_id: str) -> Asset | None:
        """Return one asset by id, or None when it is absent."""

    def save_asset(self, asset: Asset) -> Asset:
        """Create or replace an asset record and return the saved DTO."""

    def list_assets(self) -> Iterable[Asset]:
        """Return catalog assets visible to the repository implementation."""

    def delete_asset(self, asset_id: str) -> None:
        """Delete an asset record when present."""


class AssetVersionRepository(Protocol):
    """Backend-neutral repository contract for asset versions."""

    def get_version(self, version_id: str) -> AssetVersion | None:
        """Return one asset version by id, or None when it is absent."""

    def save_version(self, version: AssetVersion) -> AssetVersion:
        """Create or replace an asset version record and return the saved DTO."""

    def list_versions(self, asset_id: str) -> Iterable[AssetVersion]:
        """Return versions for one asset."""


class AssetFileRepository(Protocol):
    """Backend-neutral repository contract for mirrored asset files."""

    def get_file(self, file_id: str) -> AssetFile | None:
        """Return one asset file by id, or None when it is absent."""

    def save_file(self, file: AssetFile) -> AssetFile:
        """Create or replace an asset file record and return the saved DTO."""

    def list_files(self, asset_id: str, version_id: str | None = None) -> Iterable[AssetFile]:
        """Return files for one asset, optionally narrowed to one version."""


class SyncJobRepository(Protocol):
    """Backend-neutral repository contract for sync job metadata."""

    def get_job(self, job_id: str) -> SyncJob | None:
        """Return one sync job by id, or None when it is absent."""

    def save_job(self, job: SyncJob) -> SyncJob:
        """Create or replace a sync job record and return the saved DTO."""

    def list_jobs(self, target_id: str | None = None) -> Iterable[SyncJob]:
        """Return sync jobs, optionally narrowed to one target."""


class LocalMirrorRepository(Protocol):
    """Aggregate local mirror repository boundary for future persistence backends."""

    assets: AssetRepository
    versions: AssetVersionRepository
    files: AssetFileRepository
    jobs: SyncJobRepository


class InMemoryAssetRepository:
    """Deterministic in-memory asset repository for local smoke tests."""

    def __init__(self) -> None:
        self.records: dict[str, Asset] = {}

    def get_asset(self, asset_id: str) -> Asset | None:
        return self.records.get(asset_id)

    def save_asset(self, asset: Asset) -> Asset:
        self.records[asset.id] = asset
        return asset

    def list_assets(self) -> list[Asset]:
        return [self.records[key] for key in sorted(self.records)]

    def delete_asset(self, asset_id: str) -> None:
        self.records.pop(asset_id, None)


class InMemoryAssetVersionRepository:
    """Deterministic in-memory asset version repository."""

    def __init__(self) -> None:
        self.records: dict[str, AssetVersion] = {}

    def get_version(self, version_id: str) -> AssetVersion | None:
        return self.records.get(version_id)

    def save_version(self, version: AssetVersion) -> AssetVersion:
        self.records[version.id] = version
        return version

    def list_versions(self, asset_id: str) -> list[AssetVersion]:
        return [self.records[key] for key in sorted(self.records) if self.records[key].asset_id == asset_id]


class InMemoryAssetFileRepository:
    """Deterministic in-memory asset file repository."""

    def __init__(self) -> None:
        self.records: dict[str, AssetFile] = {}

    def get_file(self, file_id: str) -> AssetFile | None:
        return self.records.get(file_id)

    def save_file(self, file: AssetFile) -> AssetFile:
        self.records[file.id] = file
        return file

    def list_files(self, asset_id: str, version_id: str | None = None) -> list[AssetFile]:
        files = [self.records[key] for key in sorted(self.records) if self.records[key].identity.asset_id == asset_id]
        if version_id is not None:
            files = [file for file in files if file.identity.version_id == version_id]
        return files


class InMemorySyncJobRepository:
    """Deterministic in-memory sync job repository."""

    def __init__(self) -> None:
        self.records: dict[str, SyncJob] = {}

    def get_job(self, job_id: str) -> SyncJob | None:
        return self.records.get(job_id)

    def save_job(self, job: SyncJob) -> SyncJob:
        self.records[job.id] = job
        return job

    def list_jobs(self, target_id: str | None = None) -> list[SyncJob]:
        jobs = [self.records[key] for key in sorted(self.records)]
        if target_id is not None:
            jobs = [job for job in jobs if job.identity.target_id == target_id]
        return jobs


class InMemoryLocalMirrorRepository:
    """Aggregate in-memory repository used by local export/import smoke tests."""

    def __init__(self) -> None:
        self.assets = InMemoryAssetRepository()
        self.versions = InMemoryAssetVersionRepository()
        self.files = InMemoryAssetFileRepository()
        self.jobs = InMemorySyncJobRepository()


LOCAL_MIRROR_EXPORT_SCHEMA_VERSION = 1


def export_local_mirror_repository(repository: LocalMirrorRepository) -> dict[str, Any]:
    """Export local mirror metadata without file blobs."""

    return {
        "schema_version": LOCAL_MIRROR_EXPORT_SCHEMA_VERSION,
        "assets": [asset.to_dict() for asset in repository.assets.list_assets()],
        "versions": [version.to_dict() for asset in repository.assets.list_assets() for version in repository.versions.list_versions(asset.id)],
        "files": [file.to_dict() for asset in repository.assets.list_assets() for file in repository.files.list_files(asset.id)],
        "sync_jobs": [job.to_dict() for job in _list_repository_jobs(repository)],
    }


def import_local_mirror_repository(data: dict[str, Any], repository: LocalMirrorRepository | None = None) -> LocalMirrorRepository:
    """Import local mirror metadata into a repository and return it."""

    if data.get("schema_version") != LOCAL_MIRROR_EXPORT_SCHEMA_VERSION:
        raise ValueError(f"Unsupported local mirror export schema version: {data.get('schema_version')}")
    target = repository or InMemoryLocalMirrorRepository()
    for asset_data in data.get("assets", []):
        target.assets.save_asset(_asset_from_dict(asset_data))
    for version_data in data.get("versions", []):
        target.versions.save_version(_version_from_dict(version_data))
    for file_data in data.get("files", []):
        target.files.save_file(_file_from_dict(file_data))
    jobs = getattr(target, "jobs", None)
    if jobs is not None:
        for job_data in data.get("sync_jobs", []):
            jobs.save_job(_job_from_dict(job_data))
    return target


def _list_repository_jobs(repository: LocalMirrorRepository) -> Iterable[SyncJob]:
    jobs = getattr(repository, "jobs", None)
    if jobs is None:
        return []
    return jobs.list_jobs()


def _asset_from_dict(data: dict[str, Any]) -> Asset:
    identity = AssetIdentity(**data["identity"])
    return Asset(
        id=data["id"],
        identity=identity,
        source_url=data.get("source_url", ""),
        license=data.get("license"),
        tags=list(data.get("tags", [])),
        size=data.get("size", 0),
        file_count=data.get("file_count", 0),
        checksum=data.get("checksum"),
        operational_state=data.get("operational_state", "discovered"),
        visibility=data.get("visibility", "organization"),
        metadata=dict(data.get("metadata", {})),
    )


def _version_from_dict(data: dict[str, Any]) -> AssetVersion:
    identity = AssetVersionIdentity(**data["identity"])
    return AssetVersion(
        id=data["id"],
        asset_id=data["asset_id"],
        identity=identity,
        revision=data.get("revision"),
        created_at=data.get("created_at"),
        discovered_at=data.get("discovered_at"),
        size=data.get("size", 0),
        file_count=data.get("file_count", 0),
        checksum=data.get("checksum"),
        metadata=dict(data.get("metadata", {})),
    )


def _file_from_dict(data: dict[str, Any]) -> AssetFile:
    identity = AssetFileIdentity(**data["identity"])
    return AssetFile(
        id=data["id"],
        identity=identity,
        path=data["path"],
        size=data.get("size", 0),
        sha256=data.get("sha256"),
        etag=data.get("etag"),
        mime_type=data.get("mime_type"),
        file_type=data.get("file_type", "blob"),
        local_path=data.get("local_path"),
        download_url=data.get("download_url"),
        metadata=dict(data.get("metadata", {})),
    )


def _job_from_dict(data: dict[str, Any]) -> SyncJob:
    identity = SyncJobIdentity(**data["identity"])
    return SyncJob(
        id=data["id"],
        identity=identity,
        status=data.get("status", "registered"),
        attempts=data.get("attempts", 0),
        error=data.get("error"),
        metadata=dict(data.get("metadata", {})),
    )


# -- Snapshot repository (Phase 3a) --------------------------------------------

class InMemorySnapshotRepository:
    """Deterministic in-memory snapshot repository for Phase 3a tests."""

    def __init__(self) -> None:
        self._snapshots: dict[str, ApprovedSnapshot] = {}
        self._channels: dict[str, SnapshotChannel] = {}
        self._promotions: dict[str, list[SnapshotPromotion]] = {}
        self._rollbacks: dict[str, list[SnapshotRollback]] = {}

    def save_snapshot(self, snapshot: ApprovedSnapshot) -> ApprovedSnapshot:
        self._snapshots[snapshot.id] = snapshot
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> ApprovedSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self, asset_id: str) -> list[ApprovedSnapshot]:
        return [s for s in self._snapshots.values() if s.asset_id == asset_id]

    def get_channel(self, tenant_scope: str, channel_name: str) -> SnapshotChannel | None:
        return self._channels.get(f"ch_{tenant_scope}:{channel_name}")

    def save_channel(self, channel: SnapshotChannel) -> SnapshotChannel:
        self._channels[channel.id] = channel
        return channel

    def save_promotion(self, promotion: SnapshotPromotion) -> SnapshotPromotion:
        if promotion.channel_id not in self._promotions:
            self._promotions[promotion.channel_id] = []
        self._promotions[promotion.channel_id].append(promotion)
        return promotion

    def save_rollback(self, rollback: SnapshotRollback) -> SnapshotRollback:
        if rollback.channel_id not in self._rollbacks:
            self._rollbacks[rollback.channel_id] = []
        self._rollbacks[rollback.channel_id].append(rollback)
        return rollback

    def get_promotion_history(self, channel_id: str) -> list[SnapshotPromotion]:
        return self._promotions.get(channel_id, [])

    def get_rollback_history(self, channel_id: str) -> list[SnapshotRollback]:
        return self._rollbacks.get(channel_id, [])


__all__ = [
    "AssetFileRepository",
    "AssetRepository",
    "AssetVersionRepository",
    "InMemoryAssetFileRepository",
    "InMemoryAssetRepository",
    "InMemoryAssetVersionRepository",
    "InMemoryLocalMirrorRepository",
    "InMemorySnapshotRepository",
    "InMemorySyncJobRepository",
    "LOCAL_MIRROR_EXPORT_SCHEMA_VERSION",
    "LocalMirrorRepository",
    "SyncJobRepository",
    "export_local_mirror_repository",
    "import_local_mirror_repository",
]
