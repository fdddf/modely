"""Compatibility facade for shared download reliability helpers."""

from __future__ import annotations

from .syncing.reliability import (
    ChecksumStatus,
    DownloadOptions,
    checksum_status,
    diagnose_download_error,
    is_permanent_download_error,
    normalize_download_options,
    retry_call,
    sha256_file,
    verify_sha256,
)

__all__ = [
    "DownloadOptions",
    "ChecksumStatus",
    "normalize_download_options",
    "retry_call",
    "is_permanent_download_error",
    "diagnose_download_error",
    "sha256_file",
    "verify_sha256",
    "checksum_status",
]
