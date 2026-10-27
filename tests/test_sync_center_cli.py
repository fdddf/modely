import json
import sys

import pytest

import modely
from modely import resource_sync
from modely.types import DownloadPlan, FileSummary


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["modely-ai", *args])
    modely.main()


def test_sync_center_add_and_list_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)

    run_cli(monkeypatch, "sync-center", "add", "hf://models/gpt2", "--id", "gpt2", "--local-dir", str(tmp_path / "gpt2"), "--json")
    added = json.loads(capsys.readouterr().out)
    assert added["targets"][0]["id"] == "gpt2"

    run_cli(monkeypatch, "sync-center", "list", "--json")
    listed = json.loads(capsys.readouterr().out)
    assert listed["targets"][0]["resource"] == "hf://models/gpt2"


def test_sync_center_list_human_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="local", config_dir=tmp_path)

    run_cli(monkeypatch, "sync-center", "list")
    out = capsys.readouterr().out
    assert "Sync center targets" in out
    assert "gpt2" in out


def test_sync_center_show_missing_target_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, "sync-center", "show", "missing")

    assert exc.value.code == 1
    assert "Sync target not found" in capsys.readouterr().out


def test_sync_center_plan_uses_registered_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="local", source="hf", repo_type="model", config_dir=tmp_path)

    def fake_plan(resource, **kwargs):
        return DownloadPlan(source="hf", repo_type="model", repo_id="gpt2", summary=FileSummary())

    monkeypatch.setattr(resource_sync, "create_download_plan", fake_plan)

    run_cli(monkeypatch, "sync-center", "plan", "gpt2", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["plans"] == 1
    assert payload["metadata"]["plans"][0]["repo_id"] == "gpt2"


def test_sync_center_run_uses_registered_target(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="local", source="hf", config_dir=tmp_path)
    monkeypatch.setattr(resource_sync, "sync_resource", lambda resource, **kwargs: str(tmp_path / "out"))

    run_cli(monkeypatch, "sync-center", "run", "gpt2", "--checksum", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["ok"] == 1
    assert payload["runs"][0]["path"].endswith("out")


def test_sync_center_check_uses_fingerprint(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="local", source="hf", repo_type="model", config_dir=tmp_path)
    monkeypatch.setattr(resource_sync, "get_remote_fingerprint", lambda target: "abc")

    run_cli(monkeypatch, "sync-center", "check", "gpt2", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["unchanged"] == 1


def test_sync_center_runs_filters_history(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir="local", config_dir=tmp_path)

    run_cli(monkeypatch, "sync-center", "runs", "--target", "gpt2", "--limit", "1", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["runs"] == 1
    assert payload["runs"][0]["target_id"] == "gpt2"


def test_sync_center_catalog_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)
    local_dir = tmp_path / "asset"
    local_dir.mkdir()
    (local_dir / "config.json").write_text("{}")
    resource_sync.add_target("hf://models/gpt2", id="gpt2", local_dir=str(local_dir), config_dir=tmp_path)

    run_cli(monkeypatch, "sync-center", "catalog", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["targets"] == 1
    assert "catalog" in payload["metadata"]


def test_sync_center_all_with_no_targets_returns_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(resource_sync, "default_sync_center_dir", lambda: tmp_path)

    run_cli(monkeypatch, "sync-center", "check", "--all", "--json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["targets"] == 0
