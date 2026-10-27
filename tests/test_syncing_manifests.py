"""Tests for the Phase 1a sync manifest boundary."""

from __future__ import annotations

import inspect

import pytest

from modely.manifest import create_download_manifest, read_manifest
from modely.storage.base import StoredObject
from modely.storage.checksums import sha256_file
from modely.storage.local import LocalStorageBackend
from modely.syncing import manifests
from modely.syncing.manifests import create_file_list_manifest, create_local_manifest, create_storage_manifest
from modely.types import FileInfo


def test_create_local_manifest_is_deterministic_and_checksummed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "b.txt").write_text("b")
    (root / "nested").mkdir()
    (root / "nested" / "a.json").write_text("a")
    (root / ".git").mkdir()
    (root / ".git" / "ignored").write_text("ignored")

    manifest = create_local_manifest("hf://models/org/model@main", root, checksum=True)

    assert [file.path for file in manifest.files] == ["b.txt", "nested/a.json"]
    assert manifest.files[0].sha256 == sha256_file(str(root / "b.txt"))
    assert manifest.files[1].sha256 == sha256_file(str(root / "nested" / "a.json"))
    assert manifest.metadata["kind"] == "manifest"
    assert manifest.metadata["schema_version"] == 2
    assert manifest.metadata["generation_source"] == "local_path"
    assert manifest.metadata["file_count"] == 2
    assert manifest.metadata["checksum_count"] == 2
    assert manifest.metadata["missing_checksum_count"] == 0
    assert manifest.metadata["checksum_coverage"] == 1.0


def test_create_local_manifest_filters_and_handles_single_file(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    keep = root / "keep.json"
    keep.write_text("keep")
    (root / "skip.bin").write_text("skip")

    filtered = create_local_manifest("hf://models/org/model", root, include=["*.json"], checksum=False)
    single = create_local_manifest("hf://models/org/model", keep, checksum=True)

    assert [file.path for file in filtered.files] == ["keep.json"]
    assert filtered.files[0].sha256 is None
    assert [file.path for file in single.files] == ["keep.json"]
    assert single.files[0].sha256 == sha256_file(str(keep))


def test_create_file_list_manifest_normalizes_inputs_and_rejects_unsafe_paths():
    manifest = create_file_list_manifest(
        "hf://models/org/model",
        [
            FileInfo(path="z.bin", size=3, sha256="z"),
            {"path": "a.bin", "size": 1, "sha256": "a", "ignored": True},
            StoredObject(key="nested/b.bin", size=2, sha256="b", uri="file:///nested/b.bin"),
        ],
        metadata={"extra": "value"},
    )

    assert [file.path for file in manifest.files] == ["a.bin", "nested/b.bin", "z.bin"]
    assert manifest.files[1].download_url == "file:///nested/b.bin"
    assert manifest.files[1].metadata["storage_uri"] == "file:///nested/b.bin"
    assert manifest.metadata["extra"] == "value"
    assert manifest.metadata["generation_source"] == "file_list"

    with pytest.raises(ValueError):
        create_file_list_manifest("hf://models/org/model", [FileInfo(path="../escape.bin")])

    with pytest.raises(ValueError):
        create_file_list_manifest("hf://models/org/model", [{"path": "/absolute.bin"}])


def test_create_storage_manifest_uses_stored_object_metadata(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello")
    backend = LocalStorageBackend(tmp_path / "store")
    backend.put_file("objects/source.txt", source)

    manifest = create_storage_manifest("hf://models/org/model", backend.list("objects"), storage_root="local-store")

    assert [file.path for file in manifest.files] == ["objects/source.txt"]
    assert manifest.files[0].sha256 == sha256_file(str(source))
    assert manifest.metadata["generation_source"] == "storage_objects"
    assert manifest.metadata["storage_root"] == "local-store"


def test_legacy_create_download_manifest_round_trips(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.json").write_text("{}")
    output = tmp_path / "manifest.json"

    manifest = create_download_manifest("hf://models/org/model", str(root), checksum=True, output=str(output))
    loaded = read_manifest(str(output))

    assert manifest.files[0].path == "config.json"
    assert loaded.files[0].path == "config.json"
    assert loaded.files[0].sha256 == sha256_file(str(root / "config.json"))
    assert loaded.metadata["kind"] == "manifest"


def test_syncing_manifest_module_has_no_remote_dependencies():
    source = inspect.getsource(manifests)

    assert "list_repo_files" not in source
    assert "download_resource" not in source
    assert "backend_registry" not in source
    assert "FixtureSourceAdapter" not in source
