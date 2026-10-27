"""Checksum helpers for enterprise mirror storage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChecksumStatus:
    """Result of a checksum verification attempt."""

    path: str
    ok: bool
    expected: Optional[str] = None
    actual: Optional[str] = None
    skipped: bool = False
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "ok": self.ok,
            "expected": self.expected,
            "actual": self.actual,
            "skipped": self.skipped,
            "reason": self.reason,
        }


def sha256_file(path: str) -> str:
    """Compute a file SHA256 digest."""

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: str, expected: str) -> bool:
    """Return whether a file SHA256 digest matches the expected value."""

    return sha256_file(path).lower() == expected.lower()


def checksum_status(path: str, expected: Optional[str]) -> ChecksumStatus:
    """Return checksum verification status for a local path."""

    if not expected:
        return ChecksumStatus(path=path, ok=True, skipped=True, reason="missing-expected-sha256")
    actual = sha256_file(path)
    return ChecksumStatus(path=path, ok=actual.lower() == expected.lower(), expected=expected, actual=actual)


__all__ = ["ChecksumStatus", "sha256_file", "verify_sha256", "checksum_status"]
