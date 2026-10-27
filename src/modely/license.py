"""Compatibility facade for license risk classification helpers."""

from __future__ import annotations

from .governance.license import build_license_risk, classify_license, print_license_risk
from .info import get_repo_info


def license_risk(resource: str, **kwargs) -> dict:
    """Fetch resource metadata and classify its license risk."""
    return build_license_risk(resource, get_repo_info(resource, **kwargs))


__all__ = ["classify_license", "license_risk", "print_license_risk", "get_repo_info"]
