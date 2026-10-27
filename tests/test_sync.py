"""Unit tests for sync/mirror reports."""

import json

from modely.sync import sync_resource
from modely.types import AssetAnalysis, DownloadManifest, FileInfo, FileSummary, RepoInfo


def test_sync_resource_writes_report(tmp_path, monkeypatch):
    report = tmp_path / "sync-report.json"
    local_dir = tmp_path / "downloaded"
    local_dir.mkdir()

    captured_download = {}

    def fake_download(*args, **kwargs):
        captured_download.update(kwargs)
        return str(local_dir)

    monkeypatch.setattr("modely.sync.download_resource", fake_download)
    monkeypatch.setattr(
        "modely.sync.create_download_manifest",
        lambda *a, **k: DownloadManifest("hf", "model", "org/model", local_path=str(local_dir), files=[FileInfo("config.json")]),
    )
    monkeypatch.setattr(
        "modely.analyze.analyze_resource",
        lambda *a, **k: AssetAnalysis(RepoInfo("hf", "model", "org/model"), FileSummary(total_files=1, selected_files=1)),
    )

    path = sync_resource("hf://models/org/model", local_dir=str(local_dir), report=str(report), analyze=True, deep=True, checksum=True)

    data = json.loads(report.read_text())
    assert path == str(local_dir)
    assert captured_download["checksum"] is True
    assert data["status"] == "ok"
    assert data["resource"] == "hf://models/org/model"
    assert data["manifest"]["repo_id"] == "org/model"
    assert data["analysis"]["info"]["repo_id"] == "org/model"


def test_sync_resource_report_can_include_comparison(tmp_path, monkeypatch):
    report = tmp_path / "sync-report.json"
    local_dir = tmp_path / "downloaded"
    local_dir.mkdir()

    monkeypatch.setattr("modely.sync.download_resource", lambda *a, **k: str(local_dir))
    monkeypatch.setattr(
        "modely.sync.create_download_manifest",
        lambda *a, **k: DownloadManifest("hf", "model", "org/model", local_path=str(local_dir), files=[]),
    )

    captured_compare = {}

    class FakeComparison:
        warnings = ["left: warning"]

        def to_dict(self):
            return {"same_license": True}

    def fake_compare(*args, **kwargs):
        captured_compare["args"] = args
        captured_compare["kwargs"] = kwargs
        return FakeComparison()

    monkeypatch.setattr("modely.compare.compare_resources", fake_compare)

    sync_resource("hf://models/org/model", local_dir=str(local_dir), report=str(report), compare_to="ms://models/org/model", deep=True)

    data = json.loads(report.read_text())
    assert captured_compare["args"] == ("hf://models/org/model", "ms://models/org/model")
    assert captured_compare["kwargs"]["include_files"] is True
    assert captured_compare["kwargs"]["include_card"] is True
    assert captured_compare["kwargs"]["include_formats"] is True
    assert captured_compare["kwargs"]["deep"] is True
    assert data["comparison"] == {"same_license": True}
    assert data["warnings"] == ["left: warning"]
