"""Compatibility facade for local and cache asset catalog helpers."""

from __future__ import annotations

from .common import cache
from .cataloging.catalog import (
    catalog_from_cache as _catalog_from_cache,
    catalog_from_directory,
    catalog_summary,
    diff_catalogs,
    export_catalog,
    find_manifest_file,
    list_catalog_snapshots,
    print_catalog_diff,
    print_catalog_report,
    read_catalog_report,
    scan_catalog as _scan_catalog,
    snapshot_catalog,
    write_catalog_report,
)


def catalog_from_cache(cache_dir=None):
    """Return catalog entries from the modely cache."""
    return _catalog_from_cache(cache_dir, cache_module=cache)


def scan_catalog(*args, **kwargs):
    """Scan a local directory or modely cache into a catalog report."""
    return _scan_catalog(*args, **kwargs)


__all__ = [
    "scan_catalog",
    "catalog_from_cache",
    "catalog_from_directory",
    "find_manifest_file",
    "catalog_summary",
    "print_catalog_report",
    "write_catalog_report",
    "read_catalog_report",
    "diff_catalogs",
    "print_catalog_diff",
    "export_catalog",
    "snapshot_catalog",
    "list_catalog_snapshots",
    "cache",
]
