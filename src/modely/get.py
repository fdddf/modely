"""Compatibility facade for unified download helpers."""

from __future__ import annotations

from .application.downloads import download_resource as _download_resource, _verify_download_checksums as _verify_download_checksums_impl
from .application.downloads import _default_prefer, _download_ref, _fallback_refs_for_uri, _finalize_download, _local_download_path, _resolve_equivalent_ref
from .common import cache as modely_cache
from . import files as files_module


def download_resource(*args, **kwargs):
    """Download a resource by URI, explicit source, or auto/fallback source order."""
    kwargs.setdefault("cache_module", modely_cache)
    kwargs.setdefault("list_repo_files_func", files_module.list_repo_files)
    return _download_resource(*args, **kwargs)


def _verify_download_checksums(*args, **kwargs):
    kwargs.setdefault("list_repo_files_func", files_module.list_repo_files)
    return _verify_download_checksums_impl(*args, **kwargs)


__all__ = ["download_resource", "_verify_download_checksums", "modely_cache"]
