"""Tests for storage checksum primitives and reliability compatibility."""

from __future__ import annotations

import inspect

from modely.storage import checksums
from modely.syncing import reliability


def test_storage_checksum_primitives_are_source_of_truth(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello")
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    assert checksums.sha256_file(str(path)) == expected
    assert checksums.verify_sha256(str(path), expected)

    status = checksums.checksum_status(str(path), expected)
    assert status.ok
    assert status.actual == expected
    assert status.to_dict()["path"] == str(path)


def test_syncing_reliability_reexports_storage_checksum_contracts(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello")

    assert reliability.sha256_file is checksums.sha256_file
    assert reliability.verify_sha256 is checksums.verify_sha256
    assert reliability.checksum_status is checksums.checksum_status
    assert reliability.ChecksumStatus is checksums.ChecksumStatus
    assert reliability.checksum_status(str(path), None).skipped


def test_storage_checksums_do_not_import_syncing_reliability():
    source = inspect.getsource(checksums)
    assert "syncing.reliability" not in source
