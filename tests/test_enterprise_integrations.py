"""Tests for Phase 3c: MLOps integrations and platform handoff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modely.cataloging.repository import InMemoryLocalMirrorRepository, InMemorySnapshotRepository
from modely.domain.assets import Asset, AssetIdentity
from modely.domain.files import AssetFile, AssetFileIdentity
from modely.domain.versions import AssetVersion, AssetVersionIdentity
from modely.governance.api_tokens import InMemoryTokenRepository, create_token
from modely.governance.audit import record_audit_event
from modely.governance.service_accounts import InMemoryServiceAccountRepository, create_service_account
from modely.integrations.dvc import dvc_import_from_modely, dvc_lock_modely_asset, get_dvc_capability
from modely.integrations.mlflow import get_mlflow_capability, log_modely_artifact, register_modely_model, resolve_approved_for_mlflow
from modely.reproducibility.resolver import resolve_approved_asset
from modely.reproducibility.snapshots import create_snapshot
from modely.server.routes.reproducibility import record_usage_event_route, resolve_approved_route


# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
def resolver_fixture():
    repo = InMemoryLocalMirrorRepository()
    snap_repo = InMemorySnapshotRepository()

    asset = Asset(id="hf:model:org--model", identity=AssetIdentity(source="hf", repo_type="model", repo_id="org/model", revision="main"), license="apache-2.0")
    repo.assets.save_asset(asset)
    version = AssetVersion(id="v1", asset_id="hf:model:org--model", identity=AssetVersionIdentity(asset_id="hf:model:org--model", revision="v1", source="hf", repo_id="org/model"), revision="v1")
    repo.versions.save_version(version)
    repo.files.save_file(AssetFile(id="f1", identity=AssetFileIdentity(asset_id="hf:model:org--model", version_id="v1", revision="v1", path="config.json"), path="config.json", size=100, sha256="abc", local_path="assets/test/config.json"))

    snap = create_snapshot(asset_id="hf:model:org--model", version_id="v1", manifest_digest="sha256:abc123def456", channel_name="production", repository=snap_repo)

    sa_repo = InMemoryServiceAccountRepository()
    token_repo = InMemoryTokenRepository()
    sa = create_service_account(name="CI Bot", roles=["Developer"], repository=sa_repo)
    token, secret = create_token(service_account_id=sa.id, scopes=["asset:read", "asset:download"], repository=token_repo)

    return repo, snap_repo, snap, token, secret


class ResolverService:
    def __init__(self, snap_repo):
        self._snap_repo = snap_repo

    def resolve_approved_asset(self, **kwargs):
        return resolve_approved_asset(snapshot_service=self._snap_repo, **kwargs)


class UsageService:
    def record_usage_event(self, **kwargs):
        record_audit_event("platform.usage", resource=kwargs.get("asset_id", ""), status="ok", metadata=kwargs)
        return {"audit_ref": "aud_123", "status": "recorded"}


# -- MLflow adapter tests ------------------------------------------------------


def test_get_mlflow_capability():
    cap = get_mlflow_capability()
    assert cap.available is True
    assert cap.name == "MLflow"
    assert cap.supports["log_artifact"] is True


def test_resolve_approved_for_mlflow(resolver_fixture):
    repo, snap_repo, snap, token, secret = resolver_fixture
    result = resolve_approved_for_mlflow("hf:model:org--model", snapshot_service=snap_repo, repository=repo)
    assert result["mlflow_tags"]["modely.snapshot_id"] == snap.id
    assert result["mlflow_tags"]["modely.channel"] == "production"


def test_log_modely_artifact(resolver_fixture):
    repo, snap_repo, snap, token, secret = resolver_fixture
    result = log_modely_artifact("hf:model:org--model", snapshot_id=snap.id, snapshot_service=snap_repo, repository=repo)
    assert result["status"] == "ok"
    assert result["snapshot_id"] == snap.id


def test_register_modely_model(resolver_fixture):
    repo, snap_repo, snap, token, secret = resolver_fixture
    result = register_modely_model("hf:model:org--model", snapshot_id=snap.id, model_name="test-model", snapshot_service=snap_repo, repository=repo)
    assert result["status"] == "registered"
    assert result["model_name"] == "test-model"


# -- DVC adapter tests ---------------------------------------------------------


def test_get_dvc_capability():
    cap = get_dvc_capability()
    assert cap.available is True
    assert cap.name == "DVC"
    assert cap.supports["import"] is True


def test_dvc_import_from_modely(tmp_path):
    result = dvc_import_from_modely("hf:model:org--model", "snap_001", str(tmp_path / "output"), manifest_digest="sha256:abc123")
    assert result["status"] == "ok"
    assert Path(result["dvc_file"]).exists()


def test_dvc_lock_modely_asset(tmp_path):
    result = dvc_lock_modely_asset("hf:model:org--model", "snap_001", str(tmp_path / "output"), manifest_digest="sha256:abc123", file_size=1024)
    assert result["status"] == "ok"
    assert result["size"] == 1024


# -- Platform handoff tests ----------------------------------------------------


def test_resolve_approved_route(resolver_fixture):
    repo, snap_repo, snap, token, secret = resolver_fixture
    svc = ResolverService(snap_repo)
    result = resolve_approved_route(svc, "hf:model:org--model", request_id="req_r", requested_channel="production")
    assert result["data"]["snapshot_id"] == snap.id
    assert result["data"]["download"]["mode"] == "local_reference"


def test_resolve_approved_route_not_found(resolver_fixture):
    repo, snap_repo, snap, token, secret = resolver_fixture
    svc = ResolverService(snap_repo)
    result = resolve_approved_route(svc, "hf:model:org--model", request_id="req_r", requested_channel="staging")
    assert result["error"]["code"] == "approval_required"


def test_record_usage_event_route():
    svc = UsageService()
    result = record_usage_event_route(svc, request_id="req_u", platform="training", job_id="job_1", asset_id="hf:model:org--model", snapshot_id="snap_001", manifest_digest="sha256:abc", action="deploy")
    assert result["data"]["status"] == "recorded"


def test_record_usage_event_missing_fields():
    svc = UsageService()
    result = record_usage_event_route(svc, request_id="req_u")
    assert result["error"]["code"] == "validation_error"
