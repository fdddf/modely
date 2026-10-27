"""Extended skeleton boundary tests for enterprise packages."""

from __future__ import annotations

import pytest

from modely.governance.approvals import ApprovalRequest, transition_request
from modely.governance.redaction import REDACTION, redact_mapping
from modely.governance.reports import build_governance_report
from modely.integrations import planned_capability
from modely.integrations.mlflow import get_mlflow_capability
from modely.server import create_app
from modely.server.routes.catalog import get_asset, list_assets
from modely.server.routes.sync import create_sync_job
from modely.storage.download_urls import local_download_url
from modely.storage.s3 import S3StorageBackend
from modely.storage.manifests import StorageManifest
from modely.syncing.jobs import create_sync_job as create_sync_job_contract
from modely.syncing.lifecycle import can_transition, transition_status
from modely.syncing.workers import run_sync_job


class AssetService:
    def list_assets(self):
        return [{"id": "a1", "source": "hf", "repo_type": "model", "repo_id": "org/model"}]

    def get_asset(self, asset_id):
        return {"id": asset_id, "source": "hf", "repo_type": "model", "repo_id": "org/model"}


class SyncService:
    def create_sync_job(self, **kwargs):
        return {"id": "j1", "target_id": kwargs["target_id"], "status": "registered"}


def test_governance_approval_redaction_and_report_contracts():
    request = ApprovalRequest("r1", "asset-1", "user-1")
    submitted = transition_request(request, "pending")
    approved = transition_request(submitted, "approved", reviewer="sec", reason="ok")

    assert approved.status == "approved"
    assert redact_mapping({"token": "secret", "nested": {"url": "x?api_key=123"}})["token"] == REDACTION
    report = build_governance_report("governance", audit_events=[{"token": "secret"}])
    assert report.to_dict()["audit_events"][0]["token"] == REDACTION

    with pytest.raises(ValueError):
        transition_request(approved, "rejected")


def test_syncing_job_lifecycle_and_worker_contracts():
    job = create_sync_job_contract("j1", target_id="target-1", resource="hf://models/gpt2")

    assert can_transition("registered", "syncing")
    assert transition_status("syncing", "synced") == "synced"

    done = run_sync_job(job, lambda current: {"target_id": current.identity.target_id})
    assert done.status == "synced"
    assert done.attempts == 1
    assert done.metadata["result"]["target_id"] == "target-1"


def test_server_route_adapters_are_thin_and_dependency_injected():
    app = create_app()
    health = app.call("/api/v1/health", request_id="req_test")
    assert health["data"]["status"] == "ok"
    assert health["meta"]["request_id"] == "req_test"

    assets = list_assets(AssetService(), request_id="req_a")
    asset = get_asset(AssetService(), "a1", request_id="req_b")
    job = create_sync_job(SyncService(), target_id="t1", resource="hf://models/test", request_id="req_c")

    assert assets["data"]["total"] == 1
    assert assets["meta"]["request_id"] == "req_a"
    assert asset["data"]["id"] == "a1"
    assert job["data"]["target_id"] == "t1"


def test_storage_and_integration_boundary_contracts():
    assert local_download_url("/tmp/model").to_dict()["url"] == "file:///tmp/model"
    assert StorageManifest("root", files=[{"path": "config.json"}]).to_dict()["files"][0]["path"] == "config.json"
    assert not planned_capability("Jenkins").available
    assert get_mlflow_capability().name == "MLflow"

    with pytest.raises(NotImplementedError):
        S3StorageBackend()
