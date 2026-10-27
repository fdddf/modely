"""Compatibility facade for download-only sync helpers."""

from __future__ import annotations

from .get import download_resource
from .manifest import create_download_manifest
from .syncing.resource_sync import sync_resource as _sync_resource


def sync_resource(*args, **kwargs):
    """Ensure a remote resource is materialized locally. No upload is performed."""
    kwargs.setdefault("download_resource_func", download_resource)
    kwargs.setdefault("create_download_manifest_func", create_download_manifest)
    return _sync_resource(*args, **kwargs)


__all__ = ["sync_resource", "download_resource", "create_download_manifest"]
