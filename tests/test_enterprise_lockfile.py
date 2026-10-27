"""Tests for Phase 3a-1: Enterprise lockfile schema and validation."""

from __future__ import annotations

import json

import pytest

from modely.reproducibility.lockfiles import (
    ENTERPRISE_LOCK_SCHEMA_VERSION,
    EnterpriseLockfile,
    LockfileEntry,
    read_enterprise_lock,
    read_manifest,
    validate_enterprise_lock,
    write_enterprise_lock,
    write_enterprise_lock_yaml,
    write_manifest,
)
from modely.server.routes.reproducibility import validate_lockfile
from modely.server.schemas.envelopes import generate_request_id
from modely.types import DownloadManifest, FileInfo, RepoRef
from modely.syncing.manifests import create_local_manifest


class LockfileService:
    """Thin service wrapping enterprise lockfile functions for route tests."""

    def validate_enterprise_lock(self, *, path=None, content=None, profile="production", fail_on_warnings=False):
        return validate_enterprise_lock(path=path, content=content, profile=profile, fail_on_warnings=fail_on_warnings)


# -- Enterprise lockfile write/read tests -------------------------------------


def test_write_and_read_enterprise_lockfile_json(tmp_path):
    entry = LockfileEntry(
        uri="hf://models/org/model",
        internal_asset_id="hf:model:org--model",
        pinned_revision="abc123",
        manifest_digest="sha256:def456",
        files=[{"path": "config.json", "sha256": "abc"}, {"path": "model.bin", "sha256": "def"}],
        checksums={"config.json": "abc", "model.bin": "def"},
        approved_snapshot_ref="snap_test_001",
        approved_by="admin",
        approved_at="2026-06-26T00:00:00Z",
        source_url="https://huggingface.co/org/model",
        internal_url="https://modely.internal/assets/hf:model:org--model",
    )
    lockfile = EnterpriseLockfile(resources=[entry])

    output = tmp_path / "modely.lock"
    write_enterprise_lock(lockfile, str(output))

    loaded = read_enterprise_lock(str(output))
    assert loaded.schema_version == ENTERPRISE_LOCK_SCHEMA_VERSION
    assert len(loaded.resources) == 1
    assert loaded.resources[0].uri == "hf://models/org/model"
    assert loaded.resources[0].approved_snapshot_ref == "snap_test_001"


def test_read_enterprise_lock_upgrades_v3_manifest(tmp_path):
    """Schema v3 manifests should be upgraded to enterprise format on read."""
    manifest = DownloadManifest(
        source="hf", repo_type="model", repo_id="org/model", revision="main",
        files=[FileInfo(path="config.json", size=100, sha256="abc")],
    )
    path = tmp_path / "modely_v3.lock"
    write_manifest(manifest, str(path))

    loaded = read_enterprise_lock(str(path))
    assert loaded.schema_version == ENTERPRISE_LOCK_SCHEMA_VERSION
    assert loaded.resources[0].checksums["config.json"] == "abc"
    assert loaded.metadata["upgraded_from_schema_v3"] is True


def test_validate_enterprise_lock_passed(tmp_path):
    entry = LockfileEntry(
        uri="hf://models/org/model",
        checksums={"config.json": "abc123"},
        approved_snapshot_ref="snap_001",
        policy_status="allowed",
    )
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock"
    write_enterprise_lock(lockfile, str(path))

    result = validate_enterprise_lock(path=str(path))
    assert result["summary"]["passed"] == 1
    assert result["summary"]["failed"] == 0


def test_validate_enterprise_lock_blocked_policy(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model", policy_status="blocked")
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock"
    write_enterprise_lock(lockfile, str(path))

    result = validate_enterprise_lock(path=str(path))
    assert result["summary"]["failed"] == 1
    assert "Policy blocked" in result["resources"][0]["errors"][0]


def test_validate_enterprise_lock_missing_snapshot_ref(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model", checksums={"x": "y"}, policy_status="allowed")
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock"
    write_enterprise_lock(lockfile, str(path))

    result = validate_enterprise_lock(path=str(path))
    assert len(result["resources"][0]["warnings"]) > 0


def test_validate_enterprise_lock_with_content():
    content = {"schema_version": 4, "resources": [{"uri": "hf://models/org/model", "approved_snapshot_ref": "snap_001", "policy_status": "allowed", "checksums": {"x": "y"}}]}
    result = validate_enterprise_lock(content=content)
    assert result["resources"][0]["status"] == "passed"


def test_validate_enterprise_lock_fail_on_warnings(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model", policy_status="not_evaluated")
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock"
    write_enterprise_lock(lockfile, str(path))

    result = validate_enterprise_lock(path=str(path), fail_on_warnings=True)
    assert result["resources"][0]["status"] == "failed"


def test_validate_enterprise_lock_missing_input():
    with pytest.raises(ValueError, match="Either path or content"):
        validate_enterprise_lock()


# -- YAML format tests (3a-4) -------------------------------------------------


def test_write_enterprise_lock_yaml(tmp_path):
    entry = LockfileEntry(
        uri="hf://models/org/model",
        pinned_revision="abc123",
        files=[{"path": "config.json", "sha256": "xxx"}, {"path": "model.safetensors", "sha256": "yyy"}],
        source_url="https://huggingface.co/org/model",
        internal_url="https://modely.internal/assets/...",
        approved_by="admin",
        approved_at="2026-06-26T00:00:00Z",
    )
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock.yaml"
    write_enterprise_lock_yaml(lockfile, str(path))

    assert path.exists()
    content = path.read_text()
    assert "uri:" in content
    assert "hf://models/org/model" in content
    assert "sha256: xxx" in content


def test_read_enterprise_lock_yaml(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model", pinned_revision="main", checksums={"x": "y"}, approved_snapshot_ref="snap_001", policy_status="allowed")
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock.yaml"
    write_enterprise_lock_yaml(lockfile, str(path))

    loaded = read_enterprise_lock(str(path))
    assert loaded.resources[0].uri == "hf://models/org/model"


def test_read_enterprise_lock_yml_extension(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model2", checksums={"a": "b"}, approved_snapshot_ref="snap_002", policy_status="allowed")
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock.yml"
    write_enterprise_lock_yaml(lockfile, str(path))

    loaded = read_enterprise_lock(str(path))
    assert loaded.resources[0].uri == "hf://models/org/model2"


def test_yaml_and_json_round_trip_are_equivalent(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model", pinned_revision="main", approved_snapshot_ref="snap_001", policy_status="allowed", checksums={"x": "y"})
    lockfile = EnterpriseLockfile(resources=[entry])

    json_path = tmp_path / "test.json"
    yaml_path = tmp_path / "test.yaml"
    write_enterprise_lock(lockfile, str(json_path))
    write_enterprise_lock_yaml(lockfile, str(yaml_path))

    from_json = read_enterprise_lock(str(json_path))
    from_yaml = read_enterprise_lock(str(yaml_path))

    assert from_json.resources[0].uri == from_yaml.resources[0].uri
    assert from_json.schema_version == from_yaml.schema_version


# -- API route tests ----------------------------------------------------------


def test_validate_lockfile_route_returns_envelope(tmp_path):
    entry = LockfileEntry(uri="hf://models/org/model", approved_snapshot_ref="snap_001", policy_status="allowed", checksums={"x": "y"})
    lockfile = EnterpriseLockfile(resources=[entry])
    path = tmp_path / "modely.lock"
    write_enterprise_lock(lockfile, str(path))

    svc = LockfileService()
    result = validate_lockfile(svc, request_id="req_val", lockfile_path=str(path))
    assert result["data"]["status"] == "passed"
    assert result["meta"]["request_id"] == "req_val"


def test_validate_lockfile_route_with_content():
    svc = LockfileService()
    content = {"schema_version": 4, "resources": [{"uri": "hf://models/org/model", "approved_snapshot_ref": "snap_001", "policy_status": "allowed", "checksums": {"x": "y"}}]}
    result = validate_lockfile(svc, request_id="req_val", lockfile_content=content)
    assert result["data"]["status"] == "passed"


def test_validate_lockfile_route_missing_input():
    svc = LockfileService()
    result = validate_lockfile(svc, request_id="req_val")
    assert result["error"]["code"] == "validation_error"


def test_validate_lockfile_route_not_found():
    svc = LockfileService()
    result = validate_lockfile(svc, request_id="req_val", lockfile_path="/nonexistent/path.lock")
    assert result["error"]["code"] == "not_found"
