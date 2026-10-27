"""Sync-center ownership tests for the application service layer."""

from __future__ import annotations

from modely.application import sync_center as services
from modely.syncing import center
from modely.types import CatalogReport, DownloadPlan, FileSummary


def test_application_sync_center_uses_structured_center_dependencies(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(services, "create_download_plan", lambda resource, **kwargs: calls.append(("plan", resource)) or DownloadPlan(source="hf", repo_type="model", repo_id="gpt2", summary=FileSummary()))
    monkeypatch.setattr(services, "sync_resource", lambda resource, **kwargs: calls.append(("sync", resource)) or str(tmp_path / "out"))
    monkeypatch.setattr(services, "get_remote_fingerprint", lambda target: calls.append(("check", target.resource)) or "fp")

    target = services.add_sync_target(resource="hf://models/gpt2", id="gpt2", local_dir="local", source="hf", repo_type="model", config_dir=tmp_path).targets[0]

    plan_report = services.plan_sync_targets(target_id=target.id, config_dir=tmp_path)
    run_report = services.run_sync_targets(target_id=target.id, config_dir=tmp_path)
    check_report = services.check_sync_targets(target_id=target.id, config_dir=tmp_path)

    assert plan_report.summary["plans"] == 1
    assert run_report.summary["ok"] == 1
    assert check_report.summary["unchanged"] == 1
    assert calls == [("plan", "hf://models/gpt2"), ("sync", "hf://models/gpt2"), ("check", "hf://models/gpt2")]
    assert center.load_states(tmp_path)["gpt2"].last_fingerprint == "fp"


def test_application_catalog_uses_structured_center_catalog_flow(tmp_path, monkeypatch):
    local = tmp_path / "asset"
    local.mkdir()
    services.add_sync_target(resource="hf://models/gpt2", id="gpt2", local_dir=str(local), config_dir=tmp_path)

    monkeypatch.setattr(services, "scan_catalog", lambda path: CatalogReport(root=path, summary={"total_entries": 0}))
    report = services.catalog_sync_targets(config_dir=tmp_path)

    assert report.summary["targets"] == 1
    assert report.metadata["catalog"]["metadata"]["mode"] == "sync-center"
