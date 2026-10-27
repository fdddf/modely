"""Local storage backend contract tests."""

from __future__ import annotations

import pytest

from modely.storage.local import LocalStorageBackend


EXPECTED_HELLO_SHA256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_local_storage_put_get_list_checksum_and_delete(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello")
    backend = LocalStorageBackend(tmp_path / "store")

    stored = backend.put_file("objects/source.txt", source, metadata={"kind": "fixture"})

    assert stored.key == "objects/source.txt"
    assert stored.size == 5
    assert stored.sha256 == EXPECTED_HELLO_SHA256
    assert stored.metadata == {"kind": "fixture"}
    assert backend.exists("objects/source.txt")
    assert backend.get("objects/source.txt") == b"hello"
    assert backend.checksum("objects/source.txt") == EXPECTED_HELLO_SHA256

    listed = list(backend.list("objects"))
    assert [item.key for item in listed] == ["objects/source.txt"]
    assert listed[0].sha256 == EXPECTED_HELLO_SHA256

    backend.delete("objects/source.txt")
    assert not backend.exists("objects/source.txt")


def test_local_storage_rejects_unsafe_keys(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello")
    backend = LocalStorageBackend(tmp_path / "store")

    unsafe_keys = ["", ".", "../escape.txt", "safe/../../escape.txt", "safe\\..\\escape.txt"]
    for key in unsafe_keys:
        with pytest.raises(ValueError):
            backend.put_file(key, source)
        with pytest.raises(ValueError):
            backend.exists(key)


def test_local_storage_normalizes_leading_slashes_and_backslashes(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello")
    backend = LocalStorageBackend(tmp_path / "store")

    stored = backend.put_file("/objects\\source.txt", source)

    assert stored.key == "objects/source.txt"
    assert backend.exists("objects/source.txt")
    assert backend.get("objects/source.txt") == b"hello"


def test_local_storage_capabilities_are_local_only(tmp_path):
    backend = LocalStorageBackend(tmp_path / "store")

    capabilities = backend.capabilities()

    assert capabilities.backend == "local"
    assert capabilities.local_disk
    assert capabilities.checksum
    assert not capabilities.range_read
    assert not capabilities.signed_url
    assert not capabilities.quota
    assert not capabilities.object_storage
