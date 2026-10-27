"""Tests for no-network syncing source adapters."""

from __future__ import annotations

import pytest

from modely.storage.checksums import sha256_file
from modely.syncing.adapters import FixtureSourceAdapter, SourceCredentialRef
from modely.types import FileInfo, RepoRef


def test_fixture_source_adapter_capabilities_are_no_network(tmp_path):
    credential = SourceCredentialRef(ref="cred-1", provider="fixture", scope="read", metadata={"token": "secret"})
    adapter = FixtureSourceAdapter(tmp_path, credential=credential)

    assert adapter.name == "fixture"
    assert adapter.capabilities.list_files
    assert adapter.capabilities.download_file
    assert adapter.capabilities.resolve_revision
    assert adapter.capabilities.checksum
    assert adapter.capabilities.metadata["network"] is False
    assert adapter.capabilities.metadata["credential"]["ref"] == "cred-1"
    assert adapter.capabilities.metadata["credential"]["redacted"] is True


def test_fixture_source_adapter_lists_files_stably_with_checksums(tmp_path):
    (tmp_path / "nested").mkdir()
    config = tmp_path / "config.json"
    tokenizer = tmp_path / "nested" / "tokenizer.json"
    config.write_text("{}")
    tokenizer.write_text("tokenizer")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored").write_text("ignored")
    ref = RepoRef(source="fixture", repo_type="model", repo_id="org/model", revision="main")

    files = FixtureSourceAdapter(tmp_path).list_files(ref)

    assert [file.path for file in files] == ["config.json", "nested/tokenizer.json"]
    assert files[0].size == 2
    assert files[0].sha256 == sha256_file(str(config))
    assert files[1].sha256 == sha256_file(str(tokenizer))
    assert files[0].metadata["repo_id"] == "org/model"
    assert files[0].metadata["revision"] == "main"


def test_fixture_source_adapter_downloads_file_to_directory(tmp_path):
    fixture_root = tmp_path / "fixture"
    destination = tmp_path / "out"
    (fixture_root / "nested").mkdir(parents=True)
    source = fixture_root / "nested" / "tokenizer.json"
    source.write_text("tokenizer")
    ref = RepoRef(source="fixture", repo_type="model", repo_id="org/model")

    target = FixtureSourceAdapter(fixture_root).download_file(ref, FileInfo(path="nested/tokenizer.json"), destination)

    assert target == destination / "nested" / "tokenizer.json"
    assert target.read_text() == "tokenizer"


def test_fixture_source_adapter_rejects_unsafe_paths(tmp_path):
    adapter = FixtureSourceAdapter(tmp_path)
    ref = RepoRef(source="fixture", repo_type="model", repo_id="org/model")

    for unsafe in ["", ".", "../secret", "nested/../../secret", "nested\\..\\secret", "/absolute"]:
        with pytest.raises(ValueError):
            adapter.download_file(ref, unsafe, tmp_path / "out")


def test_fixture_source_adapter_download_overwrite_behavior(tmp_path):
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    (fixture_root / "config.json").write_text("new")
    destination = tmp_path / "config.json"
    destination.write_text("old")
    ref = RepoRef(source="fixture", repo_type="model", repo_id="org/model")
    adapter = FixtureSourceAdapter(fixture_root)

    with pytest.raises(FileExistsError):
        adapter.download_file(ref, "config.json", destination)

    target = adapter.download_file(ref, "config.json", destination, overwrite=True)

    assert target == destination
    assert destination.read_text() == "new"


def test_fixture_source_adapter_resolves_revision_deterministically(tmp_path):
    adapter = FixtureSourceAdapter(tmp_path)

    assert adapter.resolve_revision(RepoRef(source="fixture", repo_type="model", repo_id="org/model", revision="main")) == "main"
    assert adapter.resolve_revision(RepoRef(source="fixture", repo_type="model", repo_id="org/model")) == "fixture"


def test_fixture_source_adapter_reports_missing_or_invalid_roots(tmp_path):
    missing = FixtureSourceAdapter(tmp_path / "missing")
    ref = RepoRef(source="fixture", repo_type="model", repo_id="org/model")

    with pytest.raises(FileNotFoundError):
        missing.list_files(ref)

    file_root = tmp_path / "file-root"
    file_root.write_text("not a directory")
    with pytest.raises(ValueError):
        FixtureSourceAdapter(file_root).list_files(ref)
