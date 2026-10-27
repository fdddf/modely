"""Compatibility facade for manifest and lockfile helpers."""

from __future__ import annotations

from .files import list_repo_files
from .get import download_resource
from .reproducibility.lockfiles import (
    create_download_manifest,
    create_lock as _create_lock,
    install_lock as _install_lock,
    lock_summary,
    migrate_lock_metadata,
    print_lock_validation,
    read_manifest,
    validate_lock,
    write_manifest,
)


def create_lock(*args, **kwargs):
    """Create a lockfile while preserving old-path monkeypatch hooks."""
    kwargs.setdefault("list_repo_files_func", list_repo_files)
    return _create_lock(*args, **kwargs)


def install_lock(*args, **kwargs):
    """Install a lockfile while preserving old-path monkeypatch hooks."""
    kwargs.setdefault("download_resource_func", download_resource)
    return _install_lock(*args, **kwargs)


__all__ = [
    "write_manifest",
    "read_manifest",
    "create_lock",
    "lock_summary",
    "install_lock",
    "create_download_manifest",
    "validate_lock",
    "print_lock_validation",
    "migrate_lock_metadata",
    "list_repo_files",
    "download_resource",
]
