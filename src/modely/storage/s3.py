"""S3-compatible storage backend integration point."""

from __future__ import annotations


class S3StorageBackend:
    """Placeholder for optional S3/MinIO storage support.

    The core package intentionally does not depend on S3 SDKs. Install/select an
    enterprise storage extra before wiring a concrete implementation here.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("S3StorageBackend requires an optional enterprise storage implementation")


__all__ = ["S3StorageBackend"]
