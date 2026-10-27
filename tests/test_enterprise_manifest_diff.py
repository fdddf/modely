"""Tests for Phase 3a-2: Manifest diff and version comparison."""

from __future__ import annotations

import pytest

from modely.cataloging.repository import InMemoryLocalMirrorRepository
from modely.domain.assets import Asset, AssetIdentity
from modely.domain.files import AssetFile, AssetFileIdentity
from modely.domain.versions import AssetVersion, AssetVersionIdentity
from modely.reproducibility.manifest_diff import (
    diff_asset_versions,
    diff_manifest_dicts,
    diff_manifests,
)
from modely.server.routes.reproducibility import diff_manifests_route
from modely.types import DownloadManifest, FileInfo


# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def versioned_repository():
    """Repository with two versions of the same asset for diff testing."""
    repo = InMemoryLocalMirrorRepository()
    asset = Asset(
        id="hf:model:org--model",
        identity=AssetIdentity(source="hf", repo_type="model", repo_id="org/model", revision="main"),
        license="apache-2.0",
        tags=["nlp"],
    )
    repo.assets.save_asset(asset)

    v1 = AssetVersion(id="v1", asset_id="hf:model:org--model", identity=AssetVersionIdentity(asset_id="hf:model:org--model", revision="v1", source="hf", repo_id="org/model"), revision="v1", metadata={"risk_level": "low"})
    repo.versions.save_version(v1)
    repo.files.save_file(AssetFile(id="f1", identity=AssetFileIdentity(asset_id="hf:model:org--model", version_id="v1", revision="v1", path="config.json"), path="config.json", size=100, sha256="aaa"))
    repo.files.save_file(AssetFile(id="f2", identity=AssetFileIdentity(asset_id="hf:model:org--model", version_id="v1", revision="v1", path="model.bin"), path="model.bin", size=500, sha256="bbb"))

    v2 = AssetVersion(id="v2", asset_id="hf:model:org--model", identity=AssetVersionIdentity(asset_id="hf:model:org--model", revision="v2", source="hf", repo_id="org/model"), revision="v2", metadata={"risk_level": "medium"})
    repo.versions.save_version(v2)
    repo.files.save_file(AssetFile(id="f3", identity=AssetFileIdentity(asset_id="hf:model:org--model", version_id="v2", revision="v2", path="config.json"), path="config.json", size=150, sha256="ccc"))
    repo.files.save_file(AssetFile(id="f4", identity=AssetFileIdentity(asset_id="hf:model:org--model", version_id="v2", revision="v2", path="tokenizer.json"), path="tokenizer.json", size=50, sha256="ddd"))

    return repo


class ManifestDiffService:
    def __init__(self, repo):
        self._repo = repo

    def diff_asset_versions(self, left_vid, right_vid):
        return diff_asset_versions(left_vid, right_vid, repository=self._repo)

    def diff_manifest_dicts(self, left, right):
        return diff_manifest_dicts(left, right)


# -- Manifest diff tests -------------------------------------------------------


def test_diff_manifests_identical():
    manifest = DownloadManifest(source="hf", repo_type="model", repo_id="org/model", revision="main", files=[FileInfo(path="config.json", size=100, sha256="abc")])
    result = diff_manifests(manifest, manifest)
    assert result["summary"]["added"] == 0
    assert result["summary"]["removed"] == 0
    assert result["summary"]["changed"] == 0


def test_diff_manifests_file_changed_size():
    left = DownloadManifest(source="hf", repo_type="model", repo_id="org/model", files=[FileInfo(path="a", size=100)])
    right = DownloadManifest(source="hf", repo_type="model", repo_id="org/model", files=[FileInfo(path="a", size=200)])
    result = diff_manifests(left, right)
    assert result["summary"]["changed"] == 1


def test_diff_manifests_file_changed_sha256():
    left = DownloadManifest(source="hf", repo_type="model", repo_id="org/model", files=[FileInfo(path="a", size=100, sha256="aaa")])
    right = DownloadManifest(source="hf", repo_type="model", repo_id="org/model", files=[FileInfo(path="a", size=100, sha256="bbb")])
    result = diff_manifests(left, right)
    assert result["summary"]["changed"] == 1


def test_diff_asset_versions_detects_file_changes(versioned_repository):
    result = diff_asset_versions("v1", "v2", repository=versioned_repository)
    assert result["summary"]["added"] == 1  # tokenizer.json is new
    assert result["summary"]["changed"] == 1  # config.json changed size
    assert result["summary"]["removed"] == 1  # model.bin removed


def test_diff_asset_versions_identical(versioned_repository):
    result = diff_asset_versions("v1", "v1", repository=versioned_repository)
    assert result["summary"]["added"] == 0
    assert result["summary"]["removed"] == 0
    assert result["summary"]["changed"] == 0


def test_diff_asset_versions_not_found(versioned_repository):
    with pytest.raises(KeyError, match="Version not found"):
        diff_asset_versions("nonexistent", "v1", repository=versioned_repository)


def test_diff_asset_versions_risk_delta(versioned_repository):
    result = diff_asset_versions("v1", "v2", repository=versioned_repository)
    assert result["risk_delta"]["changed"] is True
    assert result["risk_delta"]["left"] == "low"
    assert result["risk_delta"]["right"] == "medium"


def test_diff_manifest_dicts():
    left = {"source": "hf", "repo_type": "model", "repo_id": "x/y", "files": [{"path": "a", "size": 1}]}
    right = {"source": "hf", "repo_type": "model", "repo_id": "x/y", "files": [{"path": "a", "size": 2}]}
    result = diff_manifest_dicts(left, right)
    assert result["summary"]["changed"] == 1


# -- API route tests -----------------------------------------------------------


def test_diff_manifests_route_by_version_ids(versioned_repository):
    svc = ManifestDiffService(versioned_repository)
    result = diff_manifests_route(svc, request_id="req_diff", left_version_id="v1", right_version_id="v2")
    assert result["data"]["summary"]["added"] == 1
    assert result["meta"]["request_id"] == "req_diff"


def test_diff_manifests_route_by_inline_content(versioned_repository):
    svc = ManifestDiffService(versioned_repository)
    left = {"source": "hf", "repo_type": "model", "repo_id": "x/y", "files": [{"path": "a", "size": 1}]}
    right = {"source": "hf", "repo_type": "model", "repo_id": "x/y", "files": [{"path": "a", "size": 2}]}
    result = diff_manifests_route(svc, request_id="req_diff", left_manifest=left, right_manifest=right)
    assert result["data"]["summary"]["changed"] == 1


def test_diff_manifests_route_missing_input():
    svc = ManifestDiffService(None)
    result = diff_manifests_route(svc, request_id="req_diff")
    assert result["error"]["code"] == "validation_error"


def test_diff_manifests_route_not_found(versioned_repository):
    svc = ManifestDiffService(versioned_repository)
    result = diff_manifests_route(svc, request_id="req_diff", left_version_id="nonexistent", right_version_id="v1")
    assert result["error"]["code"] == "not_found"
