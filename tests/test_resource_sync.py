import json

import pytest

from modely import resource_sync
from modely.types import CatalogEntry, CatalogReport, DownloadPlan, FileInfo, FileSummary


def test_make_target_id_is_stable_and_safe():
    first = resource_sync.make_target_id("hf://models/Qwen/Qwen2", local_dir="./models/qwen", revision="main")
    second = resource_sync.make_target_id("hf://models/Qwen/Qwen2", local_dir="./models/qwen", revision="main")
    assert first == second
    assert "/" not in first
    assert ":" not in first


def test_add_target_persists_target_state_and_run(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(resource_sync, "record_audit_event", lambda *args, **kwargs: events.append((args, kwargs)))

    target = resource_sync.add_target(
        "hf://models/gpt2",
        id="gpt2",
        local_dir=str(tmp_path / "gpt2"),
        token_env="HF_TOKEN",
        labels=["llm"],
        config_dir=tmp_path,
    )

    assert target.id == "gpt2"
    assert resource_sync.load_targets(tmp_path)[0].token_env == "HF_TOKEN"
    assert resource_sync.load_states(tmp_path)["gpt2"].status == "registered"
    assert resource_sync.list_runs(config_dir=tmp_path)[0].action == "add"
    assert events[0][0][0] == "sync-center.add"

    payload = (tmp_path / "targets.json").read_text()
    assert "HF_TOKEN" in payload
    assert "secret-token-value" not in payload


def test_duplicate_target_id_fails(tmp_path):
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="one", config_dir=tmp_path)
    with pytest.raises(ValueError):
        resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="two", config_dir=tmp_path)


def test_missing_storage_loads_empty(tmp_path):
    assert resource_sync.load_targets(tmp_path) == []
    assert resource_sync.load_states(tmp_path) == {}
    assert resource_sync.list_runs(config_dir=tmp_path) == []


def test_append_and_list_runs_filters_newest_first(tmp_path):
    target = resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="one", config_dir=tmp_path)
    other = resource_sync.add_target("hf://models/bert", id="bert", local_dir="two", config_dir=tmp_path)
    resource_sync.append_run(resource_sync.ResourceSyncRun("r1", target.id, "plan", "ok", "1"), config_dir=tmp_path)
    resource_sync.append_run(resource_sync.ResourceSyncRun("r2", other.id, "plan", "ok", "2"), config_dir=tmp_path)

    runs = resource_sync.list_runs(limit=1, target_id="gpt2", config_dir=tmp_path)
    assert len(runs) == 1
    assert runs[0].id == "r1"


def test_plan_target_maps_fields_and_updates_state(tmp_path, monkeypatch):
    captured = {}

    def fake_plan(resource, **kwargs):
        captured.update({"resource": resource, **kwargs})
        return DownloadPlan(
            source="hf",
            repo_type="model",
            repo_id="gpt2",
            files=[FileInfo(path="config.json", size=10)],
            summary=FileSummary(total_files=1, selected_files=1, total_size=10, selected_size=10),
        )

    monkeypatch.setattr(resource_sync, "create_download_plan", fake_plan)
    target = resource_sync.add_target(
        "hf://models/gpt2",
        id="gpt2",
        local_dir="local",
        include=["*.json"],
        source="hf",
        repo_type="model",
        config_dir=tmp_path,
    )

    run, plan = resource_sync.plan_target(target, token="runtime-token", config_dir=tmp_path)

    assert run.status == "ok"
    assert plan.repo_id == "gpt2"
    assert captured["resource"] == "hf://models/gpt2"
    assert captured["include"] == ["*.json"]
    assert captured["token"] == "runtime-token"
    assert resource_sync.load_states(tmp_path)["gpt2"].status == "planned"


def test_sync_target_maps_fields_and_updates_state(tmp_path, monkeypatch):
    captured = {}

    def fake_sync(resource, **kwargs):
        captured.update({"resource": resource, **kwargs})
        return str(tmp_path / "downloaded")

    monkeypatch.setattr(resource_sync, "sync_resource", fake_sync)
    target = resource_sync.add_target(
        "hf://models/gpt2",
        id="gpt2",
        local_dir="local",
        manifest="manifest.json",
        report="report.json",
        source="hf",
        config_dir=tmp_path,
    )

    run = resource_sync.sync_target(target, checksum=True, force_download=True, token="token", config_dir=tmp_path)

    assert run.status == "ok"
    assert captured["checksum"] is True
    assert captured["force_download"] is True
    assert captured["token"] == "token"
    state = resource_sync.load_states(tmp_path)["gpt2"]
    assert state.status == "synced"
    assert state.run_count == 1


def test_check_target_drift_unsupported_source(tmp_path):
    target = resource_sync.add_target("github://tools/owner/repo", id="repo", local_dir="local", source="github", repo_type="tool", config_dir=tmp_path)

    run = resource_sync.check_target_drift(target, config_dir=tmp_path)

    assert run.status == "unsupported"
    assert run.warnings
    assert resource_sync.load_states(tmp_path)["repo"].status == "unsupported"


def test_check_target_drift_detects_change(tmp_path, monkeypatch):
    monkeypatch.setattr(resource_sync, "get_remote_fingerprint", lambda target: "abc")
    target = resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="local", source="hf", repo_type="model", config_dir=tmp_path)

    first = resource_sync.check_target_drift(target, config_dir=tmp_path)
    monkeypatch.setattr(resource_sync, "get_remote_fingerprint", lambda target: "def")
    second = resource_sync.check_target_drift(target, config_dir=tmp_path)

    assert first.status == "unchanged"
    assert second.status == "drifted"
    assert resource_sync.load_states(tmp_path)["gpt2"].last_fingerprint == "def"


def test_catalog_targets_aggregates_enabled_local_dirs(tmp_path, monkeypatch):
    local_one = tmp_path / "one"
    local_two = tmp_path / "two"
    local_one.mkdir()
    local_two.mkdir()
    one = resource_sync.add_target("hf://models/one", id="one", local_dir=str(local_one), config_dir=tmp_path)
    two = resource_sync.add_target("hf://models/two", id="two", local_dir=str(local_two), config_dir=tmp_path)

    def fake_scan(path):
        return CatalogReport(
            root=path,
            entries=[CatalogEntry(id=path, local_path=path, size=1, file_count=1)],
            summary={"total_entries": 1},
        )

    monkeypatch.setattr(resource_sync, "scan_catalog", fake_scan)

    run, report = resource_sync.catalog_targets([one, two], snapshot=True, config_dir=tmp_path)

    assert run.status == "ok"
    assert len(report.entries) == 2
    assert report.summary["targets"] == 2
    assert "snapshot" in report.metadata
