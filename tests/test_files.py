"""Unit tests for unified file listing helpers."""

from modely.files import list_repo_files, print_file_tree
from modely.types import FileInfo, RepoRef


def test_list_repo_files_auto_uses_resolved_ref(monkeypatch):
    monkeypatch.setattr("modely.files.resolve_repo_ref", lambda *a, **k: RepoRef("hf", "dataset", "org/data"))

    captured = {}

    def fake_list_files(repo_id, **kwargs):
        captured["repo_id"] = repo_id
        captured.update(kwargs)
        return [FileInfo("README.md")]

    monkeypatch.setattr("modely.hf.list_files", fake_list_files)

    files = list_repo_files("org/data", repo_type="auto")

    assert files[0].path == "README.md"
    assert captured["repo_id"] == "org/data"
    assert captured["repo_type"] == "dataset"


def test_list_repo_files_explicit_uri_skips_auto_resolution(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("resolve_repo_ref should not be called for explicit URIs")

    monkeypatch.setattr("modely.files.resolve_repo_ref", fail_if_called)
    monkeypatch.setattr("modely.hf.list_files", lambda *a, **k: [FileInfo("README.md")])

    assert list_repo_files("hf://datasets/org/data")[0].path == "README.md"


def test_print_file_tree_shows_categories(capsys):
    print_file_tree([FileInfo("nested/config.json", size=10), FileInfo("README.md", size=5)])

    output = capsys.readouterr().out
    assert "README.md [card]" in output
    assert "config.json [config]" in output
