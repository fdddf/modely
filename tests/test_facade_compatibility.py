"""Facade compatibility safety net for structure migrations."""

from __future__ import annotations

import importlib

import pytest


FACADE_SYMBOLS = {
    "modely.catalog": ["scan_catalog", "catalog_from_cache", "catalog_summary", "cache"],
    "modely.sync": ["sync_resource", "download_resource", "create_download_manifest"],
    "modely.resource_sync": [
        "add_target",
        "plan_target",
        "sync_target",
        "catalog_targets",
        "create_download_plan",
        "sync_resource",
        "get_remote_fingerprint",
        "scan_catalog",
    ],
    "modely.manifest": ["create_lock", "install_lock", "validate_lock", "list_repo_files", "download_resource"],
    "modely.report": ["create_resource_report", "doctor_resource", "scan_path", "score_path"],
    "modely.scan": ["scan_resource", "scan_path", "analyze_resource"],
    "modely.score": ["score_resource", "score_path", "analyze_resource"],
    "modely.policy": ["evaluate_scan_policy", "evaluate_catalog_policy", "load_policy"],
}


@pytest.mark.parametrize("module_name,symbols", FACADE_SYMBOLS.items())
def test_facade_modules_keep_key_symbols(module_name, symbols):
    module = importlib.import_module(module_name)
    for symbol in symbols:
        assert hasattr(module, symbol), f"{module_name} lost compatibility symbol {symbol}"


def test_resource_sync_facade_and_structured_center_share_storage_behavior(tmp_path):
    facade = importlib.import_module("modely.resource_sync")
    center = importlib.import_module("modely.syncing.center")

    via_facade = facade.add_target("hf://models/gpt2", id="facade", local_dir="local", config_dir=tmp_path)
    via_center = center.add_target("hf://models/bert", id="center", local_dir="local2", config_dir=tmp_path)

    assert [target.id for target in facade.load_targets(tmp_path)] == ["facade", "center"]
    assert [target.id for target in center.load_targets(tmp_path)] == ["facade", "center"]
    assert facade.make_target_id("hf://models/gpt2") == center.make_target_id("hf://models/gpt2")
    assert via_facade.id == "facade"
    assert via_center.id == "center"


def test_report_facade_patch_points_stay_available(monkeypatch, tmp_path):
    report = importlib.import_module("modely.report")
    calls = []

    class DictLike:
        def __init__(self, payload):
            self.payload = payload

        def to_dict(self):
            return dict(self.payload)

    monkeypatch.setattr(report, "scan_path", lambda path: calls.append(("scan", path)) or DictLike({"ok": True}))
    monkeypatch.setattr(report, "score_path", lambda path: calls.append(("score", path)) or DictLike({"score": 100}))

    local = tmp_path / "asset"
    local.mkdir()
    result = report.create_resource_report(str(local), format="json")

    assert calls == [("score", str(local)), ("scan", str(local))]
    assert "scan" in result
    assert "score" in result
