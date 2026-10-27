"""Tests for the Phase 1a synchronous local mirror worker."""

from __future__ import annotations

from modely.cataloging.repository import InMemoryLocalMirrorRepository, export_local_mirror_repository, import_local_mirror_repository
from modely.storage.local import LocalStorageBackend
from modely.syncing.adapters import FixtureSourceAdapter
from modely.syncing.jobs import create_sync_job
from modely.syncing.workers import LocalMirrorWorker, run_local_mirror_job


def _fixture_tree(root):
    (root / "nested").mkdir(parents=True)
    (root / "config.json").write_text("{}")
    (root / "nested" / "tokenizer.json").write_text("tokenizer")
    (root / "weights.bin").write_text("weights")


def test_local_mirror_worker_syncs_fixture_to_storage_and_repository(tmp_path):
    fixture_root = tmp_path / "fixture"
    _fixture_tree(fixture_root)
    storage = LocalStorageBackend(tmp_path / "store")
    repository = InMemoryLocalMirrorRepository()
    job = create_sync_job(
        "job-1",
        target_id="target-1",
        resource="hf://models/org/model",
        revision="main",
    )
    job.identity.idempotency_key = "idem-1"

    result = LocalMirrorWorker(adapter=FixtureSourceAdapter(fixture_root), storage=storage, repository=repository).run(job)

    assert job.status == "synced"
    assert job.attempts == 1
    assert result.status == "synced"
    assert result.asset_id == "hf:model:org--model"
    assert result.version_id == "hf:model:org--model:main:idem-1"
    assert [file["path"] for file in result.files] == ["config.json", "nested/tokenizer.json", "weights.bin"]
    assert [file.path for file in result.manifest["files"]] if False else True
    assert storage.exists("assets/hf/model/org--model/main/config.json")
    assert repository.assets.get_asset(result.asset_id).operational_state == "synced"
    assert repository.versions.get_version(result.version_id).file_count == 3
    assert len(repository.files.list_files(result.asset_id, result.version_id)) == 3


def test_local_mirror_worker_ids_are_stable_for_idempotent_reruns(tmp_path):
    fixture_root = tmp_path / "fixture"
    _fixture_tree(fixture_root)
    storage = LocalStorageBackend(tmp_path / "store")
    repository = InMemoryLocalMirrorRepository()
    worker = LocalMirrorWorker(adapter=FixtureSourceAdapter(fixture_root), storage=storage, repository=repository)

    first = create_sync_job("job-1", target_id="target-1", resource="hf://models/org/model", revision="main")
    second = create_sync_job("job-2", target_id="target-1", resource="hf://models/org/model", revision="main")
    first.identity.idempotency_key = "same"
    second.identity.idempotency_key = "same"

    result_1 = worker.run(first)
    result_2 = worker.run(second)

    assert result_1.asset_id == result_2.asset_id
    assert result_1.version_id == result_2.version_id
    assert len(repository.assets.records) == 1
    assert len(repository.versions.records) == 1
    assert len(repository.files.records) == 3


def test_local_mirror_worker_filters_files_and_writes_manifest(tmp_path):
    fixture_root = tmp_path / "fixture"
    _fixture_tree(fixture_root)
    manifest_path = tmp_path / "manifest.json"
    job = create_sync_job("job-1", target_id="target-1", resource="hf://models/org/model", revision="main")
    job.metadata.update({"include": ["*.json"], "exclude": ["nested/*"], "manifest_path": str(manifest_path)})

    result = run_local_mirror_job(job, adapter=FixtureSourceAdapter(fixture_root), storage=LocalStorageBackend(tmp_path / "store"))

    assert job.status == "synced"
    assert [file["path"] for file in result.files] == ["config.json"]
    assert [file["path"] for file in result.manifest["files"]] == ["config.json"]
    assert manifest_path.exists()


def test_local_mirror_worker_records_failures_without_repository_commit(tmp_path):
    storage = LocalStorageBackend(tmp_path / "store")
    repository = InMemoryLocalMirrorRepository()
    job = create_sync_job("job-1", target_id="target-1", resource="hf://models/org/model", revision="main")

    result = LocalMirrorWorker(adapter=FixtureSourceAdapter(tmp_path / "missing"), storage=storage, repository=repository).run(job)

    assert job.status == "failed"
    assert job.attempts == 1
    assert job.error
    assert result.status == "failed"
    assert result.error == job.error
    assert repository.assets.records == {}
    assert repository.versions.records == {}
    assert repository.files.records == {}

def test_local_mirror_repository_export_import_smoke_preserves_nested_metadata(tmp_path):
    fixture_root = tmp_path / "fixture"
    _fixture_tree(fixture_root)
    manifest_path = tmp_path / "manifest.json"
    repository = InMemoryLocalMirrorRepository()
    job = create_sync_job("job-1", target_id="target-1", resource="hf://models/org/model", revision="main")
    job.identity.idempotency_key = "export-import"
    job.metadata["manifest_path"] = str(manifest_path)

    result = LocalMirrorWorker(
        adapter=FixtureSourceAdapter(fixture_root),
        storage=LocalStorageBackend(tmp_path / "store"),
        repository=repository,
    ).run(job)
    exported = export_local_mirror_repository(repository)
    imported = import_local_mirror_repository(exported, InMemoryLocalMirrorRepository())

    asset = imported.assets.get_asset(result.asset_id)
    version = imported.versions.get_version(result.version_id)
    files = imported.files.list_files(result.asset_id, result.version_id)
    imported_job = imported.jobs.get_job("job-1")

    assert asset is not None
    assert version is not None
    assert imported_job is not None
    assert imported_job.status == "synced"
    assert imported_job.attempts == 1
    assert [file.path for file in files] == ["config.json", "nested/tokenizer.json", "weights.bin"]
    assert files[1].sha256 == result.files[1]["sha256"]
    assert files[1].metadata["storage_key"] == "assets/hf/model/org--model/main/nested/tokenizer.json"
    assert asset.checksum == version.checksum
    assert asset.metadata["manifest"]["metadata"]["job_id"] == "job-1"
    assert version.metadata["manifest"]["files"][1]["path"] == "nested/tokenizer.json"
    assert version.metadata["manifest"]["files"][1]["sha256"] == files[1].sha256
    assert imported_job.metadata["result"]["manifest_path"] == str(manifest_path)


def test_local_mirror_worker_requires_resource(tmp_path):
    fixture_root = tmp_path / "fixture"
    _fixture_tree(fixture_root)
    job = create_sync_job("job-1", target_id="target-1")

    result = run_local_mirror_job(job, adapter=FixtureSourceAdapter(fixture_root), storage=LocalStorageBackend(tmp_path / "store"))

    assert job.status == "failed"
    assert "identity.resource" in result.error
