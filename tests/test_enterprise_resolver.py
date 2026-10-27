"""Tests for Phase 3b-4: Enterprise resolve/install flows."""

from __future__ import annotations

import pytest

from modely.cataloging.repository import InMemoryLocalMirrorRepository, InMemorySnapshotRepository
from modely.domain.assets import Asset, AssetIdentity
from modely.domain.files import AssetFile, AssetFileIdentity
from modely.domain.versions import AssetVersion, AssetVersionIdentity
from modely.reproducibility.resolver import install_approved_asset, resolve_approved_asset
from modely.reproducibility.snapshots import create_snapshot, promote_snapshot


@pytest.fixture
def resolver_fixtures():
    """Set up repository + snapshot service with approved assets."""
    repo = InMemoryLocalMirrorRepository()
    snap_repo = InMemorySnapshotRepository()

    asset = Asset(id="hf:model:org--model", identity=AssetIdentity(source="hf", repo_type="model", repo_id="org/model", revision="main"), license="apache-2.0")
    repo.assets.save_asset(asset)
    version = AssetVersion(id="v1", asset_id="hf:model:org--model", identity=AssetVersionIdentity(asset_id="hf:model:org--model", revision="v1", source="hf", repo_id="org/model"), revision="v1")
    repo.versions.save_version(version)
    repo.files.save_file(AssetFile(id="f1", identity=AssetFileIdentity(asset_id="hf:model:org--model", version_id="v1", revision="v1", path="config.json"), path="config.json", size=100, sha256="abc", local_path="assets/hf/model/org--model/main/config.json"))

    snap = create_snapshot(asset_id="hf:model:org--model", version_id="v1", manifest_digest="sha256:test", channel_name="production", tenant_scope="default", repository=snap_repo)
    return repo, snap_repo, snap


# -- Resolver tests ------------------------------------------------------------


def test_resolve_approved_asset(resolver_fixtures):
    repo, snap_repo, snap = resolver_fixtures
    result = resolve_approved_asset("hf:model:org--model", snapshot_service=snap_repo)
    assert result["snapshot_id"] == snap.id
    assert result["manifest_digest"] == "sha256:test"
    assert result["download"]["mode"] == "local_reference"
    assert result["channel_resolution"]["channel"] == "production"


def test_resolve_approved_asset_not_found(resolver_fixtures):
    repo, snap_repo, snap = resolver_fixtures
    with pytest.raises(ValueError, match="No approved snapshot"):
        resolve_approved_asset("hf:model:org--model", channel="staging", snapshot_service=snap_repo)


def test_install_approved_asset(resolver_fixtures):
    repo, snap_repo, snap = resolver_fixtures
    result = install_approved_asset("hf:model:org--model", "/tmp/test_dest", snapshot_service=snap_repo, repository=repo)
    assert result["file_count"] == 1
    assert result["files_downloaded"][0]["path"] == "config.json"
    assert result["reproducibility_metadata"]["snapshot_ref"] == snap.id


def test_install_approved_asset_no_storage(resolver_fixtures):
    repo, snap_repo, snap = resolver_fixtures
    # Without storage, install returns metadata only
    result = install_approved_asset("hf:model:org--model", "/tmp/test_dest", snapshot_service=snap_repo)
    assert result["file_count"] == 0  # No storage = no files downloaded
    assert result["snapshot_id"] == snap.id
