"""Unit tests for local and cache catalog helpers."""

import json
from unittest.mock import patch

from modely.catalog import (catalog_from_cache, catalog_from_directory, diff_catalogs, export_catalog,
                            list_catalog_snapshots, print_catalog_diff, print_catalog_report, scan_catalog,
                            snapshot_catalog)
from modely.manifest import write_manifest
from modely.types import DownloadManifest, FileInfo


def test_catalog_from_directory_detects_asset(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    (model / "tokenizer.json").write_text("{}")

    entries = catalog_from_directory(str(tmp_path))

    assert len(entries) == 1
    assert entries[0].id == "model-a"
    assert entries[0].file_count == 2
    assert entries[0].size > 0


def test_catalog_from_directory_uses_lock_metadata(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    lock = model / "modely.lock"
    write_manifest(DownloadManifest("hf", "model", "org/model", revision="main", files=[FileInfo("config.json", size=2)]), str(lock))

    entry = catalog_from_directory(str(tmp_path))[0]

    assert entry.source == "hf"
    assert entry.repo_type == "model"
    assert entry.repo_id == "org/model"
    assert entry.revision == "main"
    assert entry.lock_path == str(lock)


def test_catalog_from_cache(monkeypatch):
    monkeypatch.setattr("modely.catalog.cache.list_cache", lambda cache_dir=None, detail=True: [
        {
            "source": "hf",
            "repo_type": "model",
            "repo_id": "org/model",
            "revision": "main",
            "path": "/tmp/cache/model",
            "size": 123,
            "size_str": "123 B",
            "files": [{"name": "config.json", "size": 2}],
        }
    ])

    entries = catalog_from_cache("/tmp/cache")

    assert len(entries) == 1
    assert entries[0].source == "hf"
    assert entries[0].file_count == 1
    assert entries[0].metadata["origin"] == "cache"


def test_scan_catalog_summary_and_local_enrichment(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    report = scan_catalog(str(tmp_path), include_scores=True, include_scan=True, use_remote=False)

    assert report.summary["total_entries"] == 1
    assert report.summary["by_source"] == {"unknown": 1}
    assert report.entries[0].score["score"] >= 0
    assert report.entries[0].scan["risk_level"] in {"none", "low", "medium", "high"}
    assert report.warnings == []


def test_print_catalog_json(tmp_path, capsys):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    print_catalog_report(scan_catalog(str(tmp_path)), as_json=True)
    parsed = json.loads(capsys.readouterr().out)

    assert parsed["summary"]["total_entries"] == 1
    assert parsed["entries"][0]["id"] == "model-a"


def test_print_catalog_human(tmp_path, capsys):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    print_catalog_report(scan_catalog(str(tmp_path)))
    out = capsys.readouterr().out

    assert "Total entries" in out
    assert "model-a" in out


def test_scan_catalog_from_cache(monkeypatch):
    monkeypatch.setattr("modely.catalog.cache.get_cache_dir", lambda cache_dir=None: "/tmp/cache")
    monkeypatch.setattr("modely.catalog.cache.list_cache", lambda cache_dir=None, detail=True: [
        {"source": "ms", "repo_type": "dataset", "repo_id": "org/data", "revision": "v1", "path": "/tmp/data", "size": 10, "files": []}
    ])

    report = scan_catalog(from_cache=True)

    assert report.root == "/tmp/cache"
    assert report.summary["by_source"] == {"ms": 1}


def test_catalog_local_enrichment(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    (model / "weights.pkl").write_text("pickle")

    report = scan_catalog(str(tmp_path), include_scores=True, include_scan=True)

    assert report.entries[0].score["score"] >= 0
    assert report.entries[0].scan["risk_level"] == "high"


def test_diff_catalogs_detects_changes(tmp_path):
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_model = old_root / "model-a"
    new_model = new_root / "model-a"
    old_model.mkdir(parents=True)
    new_model.mkdir(parents=True)
    (old_model / "config.json").write_text("{}")
    (new_model / "config.json").write_text("{}")
    (new_model / "tokenizer.json").write_text("{}")

    diff = diff_catalogs(scan_catalog(str(old_root)), scan_catalog(str(new_root)))

    assert diff["summary"]["changed"] == 1
    assert "file_count" in diff["changed"][0]["changes"]


def test_diff_catalogs_detects_added_and_removed(tmp_path):
    old_root = tmp_path / "old-root"
    new_root = tmp_path / "new-root"
    old_model = old_root / "old-model"
    new_model = new_root / "new-model"
    old_model.mkdir(parents=True)
    new_model.mkdir(parents=True)
    (old_model / "config.json").write_text("{}")
    (new_model / "config.json").write_text("{}")

    diff = diff_catalogs(scan_catalog(str(old_root)), scan_catalog(str(new_root)))

    assert diff["summary"] == {"added": 1, "removed": 1, "changed": 0}
    assert diff["added"][0]["id"] == "new-model"
    assert diff["removed"][0]["id"] == "old-model"


def test_print_catalog_diff_human_includes_details(tmp_path, capsys):
    old_root = tmp_path / "old-root"
    new_root = tmp_path / "new-root"
    old_model = old_root / "old-model"
    new_model = new_root / "new-model"
    old_model.mkdir(parents=True)
    new_model.mkdir(parents=True)
    (old_model / "config.json").write_text("{}")
    (new_model / "config.json").write_text("{}")

    print_catalog_diff(diff_catalogs(scan_catalog(str(old_root)), scan_catalog(str(new_root))))
    out = capsys.readouterr().out

    assert "Added entries:" in out
    assert "new-model" in out
    assert "Removed entries:" in out
    assert "old-model" in out


def test_export_catalog_csv(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    (model / "weights.pkl").write_text("pickle")
    report = scan_catalog(str(tmp_path), include_scores=True, include_scan=True)

    csv_text = export_catalog(report)

    assert "id,source,repo_type" in csv_text
    assert "model-a" in csv_text
    assert "score,grade,risk_level,finding_count" in csv_text
    assert "high" in csv_text


def test_export_catalog_rejects_unsupported_format(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")

    try:
        export_catalog(scan_catalog(str(tmp_path)), format="jsonl")
    except ValueError as exc:
        assert "Unsupported catalog export format" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_catalog_snapshots(tmp_path):
    model = tmp_path / "model-a"
    model.mkdir()
    (model / "config.json").write_text("{}")
    history = tmp_path / "history"

    path = snapshot_catalog(scan_catalog(str(tmp_path)), history_dir=str(history), name="catalog-test.json")
    snapshots = list_catalog_snapshots(str(history))

    assert path.endswith("catalog-test.json")
    assert snapshots[0]["path"] == path


def test_catalog_snapshots_empty_history(tmp_path):
    assert list_catalog_snapshots(str(tmp_path / "missing-history")) == []


def test_asset_to_response_uses_governance_engine_for_risk_level():
    """When item has no cached risk_level, _asset_to_response should use _evaluate_asset_policy."""

    from modely.server.routes.catalog import _asset_to_response

    item = {
        "id": "ms:model:test/repo:main",
        "source": "ms",
        "repo_type": "model",
        "repo_id": "test/repo",
        "revision": "main",
        "license": None,
        "file_count": 15,
        "tags": ["pytorch", "audio"],
        "size": 1024,
        "operational_state": "discovered",
        "visibility": "organization",
        "metadata": {},
    }

    # Simulate governance engine returning "high" for missing license
    with patch("modely.server.routes.catalog._evaluate_asset_policy") as mock_eval:
        mock_eval.return_value = ({}, "high", "needs_attention", ["missing_license"])
        response = _asset_to_response(item)
        mock_eval.assert_called_once()

    assert response.to_dict()["metadata"]["risk_level"] == "high"

    # When item already has a risk_level, governance engine should NOT be called
    item_cached = {**item, "risk_level": "low"}
    with patch("modely.server.routes.catalog._evaluate_asset_policy") as mock_eval:
        response = _asset_to_response(item_cached)
        mock_eval.assert_not_called()

    assert response.to_dict()["metadata"]["risk_level"] == "low"
