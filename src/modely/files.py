"""Compatibility facade for unified file listing helpers."""

from __future__ import annotations

from .application.file_queries import (
    classify_file,
    do_dry_run,
    filter_files,
    format_file_size,
    list_repo_files as _list_repo_files,
    print_file_list,
    print_file_summary,
    print_file_tree,
    summarize_files,
)
from .info import resolve_repo_ref


def list_repo_files(*args, **kwargs):
    """List files for any supported source."""
    kwargs.setdefault("resolve_repo_ref_func", resolve_repo_ref)
    return _list_repo_files(*args, **kwargs)


__all__ = [
    "format_file_size",
    "list_repo_files",
    "filter_files",
    "classify_file",
    "summarize_files",
    "print_file_summary",
    "print_file_list",
    "print_file_tree",
    "do_dry_run",
    "resolve_repo_ref",
]
