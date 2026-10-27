"""Compatibility facade for resource report helpers."""

from __future__ import annotations

from .doctor import doctor_resource
from .reporting.service import create_resource_report as _create_resource_report
from .scan import scan_path
from .score import score_path


def create_resource_report(resource: str, *, format: str = "markdown", **kwargs) -> str:
    """Create a simple resource report from doctor signals."""
    return _create_resource_report(
        resource,
        format=format,
        doctor_func=doctor_resource,
        scan_path_func=scan_path,
        score_path_func=score_path,
        **kwargs,
    )


__all__ = ["create_resource_report", "doctor_resource", "scan_path", "score_path"]
