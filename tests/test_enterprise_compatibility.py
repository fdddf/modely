"""Compatibility safety tests for the enterprise package structure."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

import modely
from modely.types import FileInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELY_ROOT = PROJECT_ROOT / "src" / "modely"


LEGACY_IMPORTS = [
    "modely.catalog",
    "modely.sync",
    "modely.auth",
    "modely.audit",
    "modely.policy",
    "modely.manifest",
    "modely.resource_sync",
    "modely.report",
    "modely.scan",
    "modely.score",
    "modely.compare",
    "modely.files",
    "modely.get",
    "modely.info",
    "modely.plan",
    "modely.version",
    "modely.mirror",
    "modely.card",
    "modely.analyze",
    "modely.labels",
    "modely.resolve",
    "modely.search",
    "modely.common.cache",
    "modely.hf",
    "modely.modelscope",
    "modely.github",
    "modely.kaggle",
]

ENTERPRISE_IMPORTS = [
    "modely.application",
    "modely.domain",
    "modely.cataloging",
    "modely.syncing",
    "modely.governance",
    "modely.reproducibility",
    "modely.integrations",
    "modely.intelligence",
    "modely.reporting",
    "modely.storage",
    "modely.server",
    "modely.server.routes.health",
    "modely.server.routes.catalog",
    "modely.server.routes.sync",
    "modely.server.routes.auth",
    "modely.server.routes.governance",
    "modely.server.routes.reports",
    "modely.server.schemas.assets",
    "modely.server.schemas.sync",
    "modely.server.schemas.governance",
    "modely.server.schemas.reports",
    "modely.application.downloads",
    "modely.application.file_queries",
    "modely.application.repo_queries",
    "modely.application.download_plans",
    "modely.cataloging.catalog",
    "modely.cataloging.cards",
    "modely.cataloging.labels",
    "modely.cataloging.service",
    "modely.intelligence.analysis",
    "modely.intelligence.scanning",
    "modely.intelligence.scoring",
    "modely.reproducibility.comparison",
    "modely.reproducibility.versions",
    "modely.reproducibility.mirror",
    "modely.reproducibility.manifest_diff",
    "modely.reproducibility.ci_gate",
    "modely.storage.base",
    "modely.storage.local",
    "modely.storage.checksums",
    "modely.reporting.markdown",
    "modely.reporting.json",
    "modely.reporting.csv",
    "modely.reporting.sarif",
    "modely.governance.permissions",
    "modely.governance.rbac",
]

COLLISION_PRONE_PACKAGES = [
    "catalog",
    "sync",
    "policy",
    "auth",
    "audit",
    "report",
    "manifest",
]


@pytest.mark.parametrize("module_name", LEGACY_IMPORTS)
def test_legacy_imports_stay_available(module_name):
    assert importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", ENTERPRISE_IMPORTS)
def test_enterprise_package_imports_stay_available(module_name):
    assert importlib.import_module(module_name)


def test_console_script_stays_anchored_to_modely_main():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["scripts"]["modely-ai"] == "modely:main"
    assert callable(modely.main)


@pytest.mark.parametrize("package_name", COLLISION_PRONE_PACKAGES)
def test_collision_prone_top_level_packages_are_not_added(package_name):
    assert not (MODELY_ROOT / package_name).is_dir()
    assert (MODELY_ROOT / f"{package_name}.py").is_file()


def test_modely_main_help_smoke(capsys):
    with pytest.raises(SystemExit) as exc:
        modely.main(["--help"])

    assert exc.value.code == 0
    assert "Command categories:" in capsys.readouterr().out


def test_hf_list_files_cli_uses_top_level_hf_module(monkeypatch, capsys):
    monkeypatch.setattr(
        "modely.hf.list_files",
        lambda *args, **kwargs: [FileInfo(path="config.json", size=12)],
    )

    modely.main(["hf", "org/model", "--list-files"])

    output = capsys.readouterr().out
    assert "[HF] org/model" in output
    assert "config.json" in output


def test_hf_dry_run_cli_uses_top_level_hf_module(monkeypatch, capsys):
    monkeypatch.setattr(
        "modely.hf.list_files",
        lambda *args, **kwargs: [FileInfo(path="weights.bin", size=1024)],
    )

    modely.main(["hf", "org/model", "--dry-run", "--include", "*.bin"])

    output = capsys.readouterr().out
    assert "[HF] org/model (dry-run)" in output
    assert "Would download:  1 file(s)" in output


def test_ms_list_files_cli_uses_top_level_modelscope_module(monkeypatch, capsys):
    class FakeHubApi:
        def __init__(self, token=None):
            self.token = token

        def get_model_files(self, repo_id, revision=None):
            return [FileInfo(path="configuration.json", size=24)]

        def get_dataset_files(self, repo_id, revision=None):
            return []

    monkeypatch.setattr("modely.modelscope.HubApi", FakeHubApi)

    modely.main(["ms", "org/model", "--list-files"])

    output = capsys.readouterr().out
    assert "[MS] org/model" in output
    assert "configuration.json" in output


def test_ms_dry_run_cli_uses_top_level_modelscope_module(monkeypatch, capsys):
    class FakeHubApi:
        def __init__(self, token=None):
            self.token = token

        def get_model_files(self, repo_id, revision=None):
            return [FileInfo(path="model.bin", size=2048)]

        def get_dataset_files(self, repo_id, revision=None):
            return []

    monkeypatch.setattr("modely.modelscope.HubApi", FakeHubApi)

    modely.main(["ms", "org/model", "--dry-run", "--include", "*.bin"])

    output = capsys.readouterr().out
    assert "[MS] org/model (dry-run)" in output
    assert "Would download:  1 file(s)" in output


def test_github_release_asset_cli_uses_top_level_github_module(monkeypatch, capsys, tmp_path):
    asset_path = tmp_path / "asset.zip"
    monkeypatch.setattr(
        "modely.github.github_release_asset_download",
        lambda *args, **kwargs: str(asset_path),
    )

    modely.main(["github", "owner/repo", "--release", "v1.0.0", "--asset", "asset.zip"])

    output = capsys.readouterr().out
    assert f"Successfully downloaded release asset to: {asset_path}" in output


def test_storage_and_health_contracts(tmp_path):
    from modely.server.routes.health import get_health
    from modely.storage.local import LocalStorageBackend

    source = tmp_path / "source.txt"
    source.write_text("hello")
    backend = LocalStorageBackend(tmp_path / "store")

    stored = backend.put_file("objects/source.txt", source)

    assert backend.exists("objects/source.txt")
    assert stored.size == 5
    health = get_health()
    assert health["data"]["status"] == "ok"
    assert "request_id" in health["meta"]

    with pytest.raises(ValueError):
        backend.exists("../escape.txt")


def test_reporting_and_governance_contracts():
    from modely.governance.rbac import Principal, check_permission
    from modely.reporting.csv import format_csv
    from modely.reporting.json import format_json
    from modely.reporting.markdown import format_markdown

    assert "# modely report" in format_markdown({"query": "x"})
    assert '"ok": true' in format_json({"ok": True})
    assert format_csv([{"name": "model"}]).replace("\r\n", "\n") == "name\nmodel\n"
    assert check_permission(Principal("u1", ["Viewer"]), "asset:read").allowed
