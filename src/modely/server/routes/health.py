"""Health and version route adapters."""

from __future__ import annotations

from ..schemas.envelopes import success_response

try:
    from importlib.metadata import version
except ImportError:  # pragma: no cover
    version = None


def get_health(request_id: str = "req_unknown") -> dict:
    """Return a dependency-free health payload wrapped in the API response envelope."""
    try:
        modely_version = version("modely-ai") if version else "unknown"
    except Exception:
        modely_version = "unknown"
    return success_response(
        {
            "status": "ok",
            "service": "modely-server",
            "version": modely_version,
        },
        request_id=request_id,
    )


def get_version(request_id: str = "req_unknown") -> dict:
    """Return the server version in the API response envelope."""
    try:
        modely_version = version("modely-ai") if version else "unknown"
    except Exception:
        modely_version = "unknown"
    return success_response({"service": "modely-server", "version": modely_version}, request_id=request_id)


__all__ = ["get_health", "get_version"]
