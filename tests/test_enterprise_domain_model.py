"""Enterprise domain contract tests."""

from __future__ import annotations

import pytest

from modely.domain import (
    APPROVAL_STATES,
    ASSET_FILE_TYPES,
    OPERATIONAL_STATES,
    POLICY_OUTCOMES,
    RESOURCE_ACTIONS,
    VISIBILITY_LEVELS,
    Asset,
    AssetFile,
    AssetFileIdentity,
    AssetIdentity,
    AssetVersion,
    AssetVersionIdentity,
    AuditEvent,
    PolicyDecision,
    ScanSummary,
    SyncJobIdentity,
    is_asset_file_type,
    is_operational_state,
    is_scan_severity,
    is_sync_job_state,
    is_sync_run_action,
    is_visibility,
)


def test_policy_and_visibility_contracts_do_not_conflict():
    assert "blocked" not in VISIBILITY_LEVELS
    assert "block" in POLICY_OUTCOMES
    assert "pending_approval" not in OPERATIONAL_STATES
    assert "approved" not in OPERATIONAL_STATES
    assert is_visibility("organization")
    assert not is_visibility("blocked")
    assert is_operational_state("synced")
    assert not is_operational_state("pending_approval")


def test_asset_and_scan_contracts_validate_core_fields():
    asset = Asset(
        id="asset-1",
        identity=AssetIdentity(source="hf", repo_type="model", namespace="org", name="model", revision="main"),
        source_url="https://example.invalid/model",
        visibility="workspace",
    )
    summary = ScanSummary(risk_level="high", counts={"high": 1}, finding_ids=["f1"])
    decision = PolicyDecision(outcome="require_approval", reasons=["secret finding"], finding_ids=["f1"])
    sync_job = SyncJobIdentity(target_id="target-1", action="sync", idempotency_key="k1")
    audit = AuditEvent(action="asset.download", actor="user-1", resource=asset.id)

    assert asset.identity.repo_type == "model"
    assert summary.risk_level == "high"
    assert decision.outcome == "require_approval"
    assert sync_job.action == "sync"
    assert audit.action == "asset.download"
    assert is_scan_severity("high")
    assert is_sync_job_state("planned")
    assert is_sync_run_action("sync")


def test_asset_version_and_file_contracts_serialize_core_fields():
    version = AssetVersion(
        id="version-1",
        asset_id="asset-1",
        identity=AssetVersionIdentity(
            asset_id="asset-1",
            version="v1",
            revision="abc123",
            source="hf",
            repo_id="org/model",
        ),
        revision="abc123",
        size=12,
        file_count=1,
        checksum="sha256:version",
        metadata={"manifest_key": "manifests/version-1.json"},
    )
    asset_file = AssetFile(
        id="file-1",
        identity=AssetFileIdentity(asset_id="asset-1", version_id="version-1", path="config.json"),
        path="config.json",
        size=12,
        sha256="sha256:file",
        metadata={"storage_key": "objects/config.json"},
    )

    version_dict = version.to_dict()
    file_dict = asset_file.to_dict()

    assert version_dict["identity"]["repo_id"] == "org/model"
    assert version_dict["metadata"]["manifest_key"] == "manifests/version-1.json"
    assert file_dict["identity"]["version_id"] == "version-1"
    assert file_dict["sha256"] == "sha256:file"
    assert file_dict["metadata"]["storage_key"] == "objects/config.json"


def test_asset_file_type_contracts_validate_values():
    assert "blob" in ASSET_FILE_TYPES
    assert is_asset_file_type("blob")
    assert not is_asset_file_type("socket")

    with pytest.raises(ValueError):
        AssetFile(
            id="file-2",
            identity=AssetFileIdentity(asset_id="asset-1", path="socket"),
            path="socket",
            file_type="socket",
        )


def test_catalog_repository_protocols_are_structurally_usable():
    from modely.cataloging.repository import AssetFileRepository, AssetRepository, AssetVersionRepository

    class InMemoryAssets:
        def __init__(self):
            self.records = {}

        def get_asset(self, asset_id):
            return self.records.get(asset_id)

        def save_asset(self, asset):
            self.records[asset.id] = asset
            return asset

        def list_assets(self):
            return list(self.records.values())

        def delete_asset(self, asset_id):
            self.records.pop(asset_id, None)

    class InMemoryVersions:
        def __init__(self):
            self.records = {}

        def get_version(self, version_id):
            return self.records.get(version_id)

        def save_version(self, version):
            self.records[version.id] = version
            return version

        def list_versions(self, asset_id):
            return [version for version in self.records.values() if version.asset_id == asset_id]

    class InMemoryFiles:
        def __init__(self):
            self.records = {}

        def get_file(self, file_id):
            return self.records.get(file_id)

        def save_file(self, file):
            self.records[file.id] = file
            return file

        def list_files(self, asset_id, version_id=None):
            files = [file for file in self.records.values() if file.identity.asset_id == asset_id]
            if version_id is not None:
                files = [file for file in files if file.identity.version_id == version_id]
            return files

    assets: AssetRepository = InMemoryAssets()
    versions: AssetVersionRepository = InMemoryVersions()
    files: AssetFileRepository = InMemoryFiles()

    asset = Asset(id="asset-1", identity=AssetIdentity(source="hf", repo_type="model"))
    version = AssetVersion(id="version-1", asset_id="asset-1", identity=AssetVersionIdentity(asset_id="asset-1"))
    asset_file = AssetFile(
        id="file-1",
        identity=AssetFileIdentity(asset_id="asset-1", version_id="version-1", path="a.bin"),
        path="a.bin",
    )

    assert assets.save_asset(asset).id == "asset-1"
    assert versions.save_version(version).id == "version-1"
    assert files.save_file(asset_file).id == "file-1"
    assert list(assets.list_assets()) == [asset]
    assert list(versions.list_versions("asset-1")) == [version]
    assert list(files.list_files("asset-1", version_id="version-1")) == [asset_file]


def test_invalid_asset_states_are_rejected():
    with pytest.raises(ValueError):
        Asset(
            id="asset-2",
            identity=AssetIdentity(source="hf", repo_type="model"),
            operational_state="pending_approval",
        )

    with pytest.raises(ValueError):
        Asset(
            id="asset-3",
            identity=AssetIdentity(source="hf", repo_type="model"),
            visibility="blocked",
        )

    with pytest.raises(ValueError):
        PolicyDecision(outcome="maybe")

    with pytest.raises(ValueError):
        ScanSummary(risk_level="extreme")
