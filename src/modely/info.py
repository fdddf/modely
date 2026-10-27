"""Compatibility facade for repository info helpers."""

from __future__ import annotations

from .application.repo_queries import (
    get_repo_info as _get_repo_info,
    print_repo_info,
    resolve_repo_ref as _resolve_repo_ref,
)


def get_repo_info(*args, **kwargs):
    """Return best-effort repository metadata for any supported source."""
    return _get_repo_info(*args, **kwargs)


def resolve_repo_ref(*args, **kwargs):
    """Resolve a resource to a concrete repository reference using metadata probes."""
    kwargs.setdefault("get_repo_info_func", get_repo_info)
    return _resolve_repo_ref(*args, **kwargs)


__all__ = ["get_repo_info", "resolve_repo_ref", "print_repo_info"]
