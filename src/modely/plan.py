"""Compatibility facade for download planning helpers."""

from __future__ import annotations

from .application.download_plans import create_download_plan as _create_download_plan, print_download_plan
from .files import list_repo_files


def create_download_plan(*args, **kwargs):
    """Create a dry-run plan describing files selected for download."""
    kwargs.setdefault("list_repo_files_func", list_repo_files)
    return _create_download_plan(*args, **kwargs)


__all__ = ["create_download_plan", "print_download_plan", "list_repo_files"]
