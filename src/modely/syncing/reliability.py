"""Shared download reliability helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

from ..storage.checksums import ChecksumStatus, checksum_status, sha256_file, verify_sha256

T = TypeVar("T")


@dataclass
class DownloadOptions:
    """Normalized reliability options for download backends."""

    retries: int = 3
    timeout: Optional[float] = None
    checksum: bool = False
    resume: bool = True
    max_workers: Optional[int] = None



def normalize_download_options(
    *,
    retries: Optional[int] = None,
    timeout: Optional[float] = None,
    checksum: bool = False,
    resume: bool = True,
    max_workers: Optional[int] = None,
) -> DownloadOptions:
    """Validate and normalize download reliability options."""
    retries = 3 if retries is None else retries
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if timeout is not None and timeout <= 0:
        raise ValueError("timeout must be > 0")
    if max_workers is not None and max_workers <= 0:
        raise ValueError("max_workers must be > 0")
    return DownloadOptions(retries=retries, timeout=timeout, checksum=checksum, resume=resume, max_workers=max_workers)


def retry_call(fn: Callable[[], T], *, retries: int = 3, label: str = "operation") -> T:
    """Call a function with simple exponential-backoff retries."""
    attempts = retries + 1
    last_error = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: PERF203 - intentional retry boundary
            last_error = exc
            if is_permanent_download_error(exc):
                raise Exception(f"{label} failed with non-retryable error: {exc}") from exc
            if attempt >= retries:
                break
            time.sleep(min(2 ** attempt, 8) * 0.1)
    raise Exception(f"{label} failed after {attempts} attempt(s): {last_error}") from last_error


def is_permanent_download_error(exc: Exception) -> bool:
    """Return whether an exception represents a non-retryable download failure."""
    status_code = _status_code(exc)
    if status_code in {400, 401, 403, 404}:
        return True
    if status_code == 429 or (status_code is not None and status_code >= 500):
        return False

    lower = str(exc).lower()
    transient_markers = (
        "429",
        "rate limit",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "connectionerror",
        "connection error",
        "502",
        "503",
        "504",
    )
    if any(marker in lower for marker in transient_markers):
        return False

    permanent_markers = (
        "400",
        "bad request",
        "401",
        "unauthorized",
        "403",
        "forbidden",
        "gated",
        "license not accepted",
        "404",
        "not found",
        "invalid repo",
        "invalid repository",
        "invalid revision",
        "revision not found",
    )
    return any(marker in lower for marker in permanent_markers)


def diagnose_download_error(source: str, exc: Exception) -> str:
    """Return a user-facing diagnostic hint for common download failures."""
    text = str(exc)
    lower = text.lower()
    hints = []
    if "401" in lower or "unauthorized" in lower:
        hints.append("authentication failed; check token or login state")
    if "403" in lower or "forbidden" in lower:
        hints.append("access forbidden; private/gated resources may require permission or license acceptance")
    if "404" in lower or "not found" in lower:
        hints.append("resource, file, or revision was not found")
    if "timeout" in lower or "timed out" in lower:
        hints.append("network timeout; try increasing --timeout or using --fallback")
    if "rate limit" in lower or "429" in lower:
        hints.append("rate limited; retry later or use an authenticated token")
    if not hints:
        hints.append("see backend error for details")
    return f"{source}: {text} ({'; '.join(hints)})"



def _status_code(exc: Exception) -> Optional[int]:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


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
