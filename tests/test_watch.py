import json
import os
import sys
from types import SimpleNamespace

import pytest

import modely
from modely import watch


def write_config(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_config_defaults_and_expands_paths(tmp_path):
    config_path = tmp_path / "watch.json"
    write_config(
        config_path,
        {
            "state_file": str(tmp_path / "state.json"),
            "targets": [{"source": "hf", "repo_type": "model", "repo_id": "gpt2"}],
        },
    )

    config, loaded_path = watch.load_config(str(config_path))

    assert loaded_path == str(config_path)
    assert config["state_file"] == str(tmp_path / "state.json")
    assert config["targets"][0]["revision"] == "main"
    assert config["targets"][0]["download"] == "snapshot"


@pytest.mark.parametrize(
    "target,error",
    [
        ({"source": "bad", "repo_type": "model", "repo_id": "x"}, "source"),
        ({"source": "hf", "repo_type": "space", "repo_id": "x"}, "repo_type"),
        ({"source": "hf", "repo_type": "model"}, "repo_id"),
        ({"source": "hf", "repo_type": "model", "repo_id": "x", "download": "bad"}, "download"),
        ({"source": "hf", "repo_type": "model", "repo_id": "x", "download": "files"}, "files"),
    ],
)
def test_load_config_validates_targets(tmp_path, target, error):
    config_path = tmp_path / "watch.json"
    write_config(config_path, {"targets": [target]})

    with pytest.raises(ValueError, match=error):
        watch.load_config(str(config_path))


def test_check_target_downloads_first_time_and_skips_unchanged(monkeypatch):
    target = watch.normalize_target({"source": "hf", "repo_type": "model", "repo_id": "gpt2"})
    state = {}
    downloads = []

    monkeypatch.setattr(watch, "get_remote_fingerprint", lambda _: "fp1")
    monkeypatch.setattr(watch, "download_target", lambda _: downloads.append("downloaded") or "/tmp/gpt2")

    first = watch.check_target(target, state)
    second = watch.check_target(target, state)

    assert first["status"] == "downloaded"
    assert second["status"] == "unchanged"
    assert downloads == ["downloaded"]
    assert state[watch.target_key(target)]["fingerprint"] == "fp1"


def test_check_target_downloads_when_fingerprint_changes(monkeypatch):
    target = watch.normalize_target({"source": "hf", "repo_type": "dataset", "repo_id": "owner/data"})
    state = {watch.target_key(target): {"fingerprint": "old"}}

    monkeypatch.setattr(watch, "get_remote_fingerprint", lambda _: "new")
    monkeypatch.setattr(watch, "download_target", lambda _: "/tmp/data")

    result = watch.check_target(target, state)

    assert result["status"] == "downloaded"
    assert state[watch.target_key(target)]["fingerprint"] == "new"
    assert state[watch.target_key(target)]["error"] is None


def test_check_target_records_error_without_replacing_fingerprint(monkeypatch):
    target = watch.normalize_target({"source": "ms", "repo_type": "model", "repo_id": "owner/model"})
    key = watch.target_key(target)
    state = {key: {"fingerprint": "old"}}

    def fail(_):
        raise RuntimeError("remote unavailable")

    monkeypatch.setattr(watch, "get_remote_fingerprint", fail)

    result = watch.check_target(target, state)

    assert result["status"] == "error"
    assert state[key]["fingerprint"] == "old"
    assert state[key]["error"] == "remote unavailable"


def test_run_watch_saves_state_after_success(tmp_path, monkeypatch):
    config_path = tmp_path / "watch.json"
    state_path = tmp_path / "state.json"
    write_config(
        config_path,
        {
            "state_file": str(state_path),
            "targets": [{"source": "hf", "repo_type": "model", "repo_id": "gpt2"}],
        },
    )

    monkeypatch.setattr(watch, "get_remote_fingerprint", lambda _: "fp1")
    monkeypatch.setattr(watch, "download_target", lambda _: "/tmp/gpt2")

    results = watch.run_watch(str(config_path))
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert results[0]["status"] == "downloaded"
    assert state["hf:model:gpt2:main"]["fingerprint"] == "fp1"


def test_default_config_has_no_placeholder_targets():
    assert watch.default_config()["targets"] == []


def test_modelscope_files_fingerprint_refreshes_when_listing_unavailable(monkeypatch):
    target = watch.normalize_target(
        {
            "source": "ms",
            "repo_type": "dataset",
            "repo_id": "owner/data",
            "download": "files",
            "files": ["README.md"],
        }
    )
    monkeypatch.setattr(watch, "_modelscope_files", lambda _, __: [])

    first = watch._ms_fingerprint(target, token=None)
    second = watch._ms_fingerprint(target, token=None)

    assert first != second


def test_modelscope_probe_warning_is_silenced(monkeypatch, capsys):
    target = watch.normalize_target(
        {
            "source": "ms",
            "repo_type": "dataset",
            "repo_id": "owner/data",
            "download": "files",
            "files": ["README.md"],
        }
    )

    class FakeApi:
        def __init__(self, token=None):
            pass

        def get_cookies(self):
            return {}

        def get_endpoint_for_read(self, repo_id, repo_type):
            return "https://example.com"

        def get_dataset_files(self, **kwargs):
            print("Warning: Could not fetch dataset file list")
            return []

    monkeypatch.setattr(watch, "HubApi", FakeApi)

    watch._ms_fingerprint(target, token=None)

    assert "Warning:" not in capsys.readouterr().out


def test_modelscope_snapshot_still_errors_when_listing_unavailable(monkeypatch):
    target = watch.normalize_target({"source": "ms", "repo_type": "dataset", "repo_id": "owner/data"})
    monkeypatch.setattr(watch, "_modelscope_files", lambda _, __: [])

    with pytest.raises(RuntimeError, match="Could not list files"):
        watch._ms_fingerprint(target, token=None)


def test_run_prints_message_when_no_targets(capsys):
    watch._print_run_results([])

    assert "No watch targets configured" in capsys.readouterr().out


def test_modelscope_pattern_filtering(monkeypatch):
    target = watch.normalize_target(
        {
            "source": "ms",
            "repo_type": "model",
            "repo_id": "owner/model",
            "allow_patterns": ["*.json"],
            "ignore_patterns": ["skip*"],
        }
    )
    monkeypatch.setattr(
        watch,
        "_modelscope_files",
        lambda _, __: [
            {"Path": "config.json", "Type": "blob"},
            {"Path": "skip.json", "Type": "blob"},
            {"Path": "weights.bin", "Type": "blob"},
            {"Path": "folder", "Type": "tree"},
        ],
    )

    assert watch._filtered_modelscope_files(target, token=None) == ["config.json"]


def test_cron_expression_daily_and_weekly():
    assert watch.build_cron_expression("day", "02:30") == "30 2 * * *"
    assert watch.build_cron_expression("week", "02:30", "mon") == "30 2 * * 1"


def test_cron_expression_rejects_invalid_time():
    with pytest.raises(ValueError, match="valid"):
        watch.build_cron_expression("day", "25:00")


def test_install_status_and_uninstall_crontab(tmp_path, monkeypatch):
    config_path = tmp_path / "watch.json"
    crontab = {"text": "# keep me\n"}

    def fake_run(args, capture_output=False, text=False, input=None):
        if args == ["crontab", "-l"]:
            return SimpleNamespace(returncode=0, stdout=crontab["text"], stderr="")
        if args == ["crontab", "-"]:
            crontab["text"] = input
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(watch.subprocess, "run", fake_run)

    entry = watch.install_crontab(str(config_path), "day", "02:30")

    assert "30 2 * * *" in entry
    assert watch.MARKER_PREFIX in crontab["text"]
    assert watch.crontab_status(str(config_path)) == entry
    assert watch.uninstall_crontab(str(config_path)) is True
    assert watch.MARKER_PREFIX not in crontab["text"]
    assert "# keep me" in crontab["text"]


def test_watch_main_init_creates_config(tmp_path, capsys):
    config_path = tmp_path / "watch.json"

    watch.main(["init", "--config", str(config_path)])

    assert config_path.exists()
    assert "Watch config created" in capsys.readouterr().out


def test_watch_main_run_prints_results(monkeypatch, capsys):
    monkeypatch.setattr(watch, "run_watch", lambda _: [{"key": "hf:model:gpt2:main", "status": "unchanged"}])

    watch.main(["run", "--config", "/tmp/watch.json"])

    output = capsys.readouterr().out
    assert "unchanged hf:model:gpt2:main" in output
    assert "Watched resources:" in output
    assert "[complete] hf model gpt2 (main) -> -" in output
    assert "All watched resources are downloaded." in output


def test_run_summary_reports_failed_resources(capsys):
    watch._print_run_results(
        [
            {
                "key": "ms:dataset:owner/data:master",
                "status": "error",
                "error": "download failed",
            }
        ]
    )

    output = capsys.readouterr().out
    assert "[failed] ms dataset owner/data (master) -> -" in output
    assert "Some watched resources failed to download." in output


def test_top_level_cli_forwards_watch_command(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["modely-ai", "watch", "status", "--config", "/tmp/watch.json"])
    monkeypatch.setattr(modely, "watch_main", lambda args: calls.append(args))

    modely.main()

    assert calls
    assert calls[0].command == "watch"
    assert calls[0].watch_command == "status"
    assert calls[0].config == "/tmp/watch.json"
