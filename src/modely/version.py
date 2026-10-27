"""Compatibility facade for revision diff helpers."""

from __future__ import annotations

from .reproducibility.versions import diff_resource_revisions as _diff_resource_revisions, print_revision_diff
from .application.file_queries import list_repo_files


def diff_resource_revisions(*args, **kwargs):
    kwargs.setdefault("list_repo_files_func", list_repo_files)
    return _diff_resource_revisions(*args, **kwargs)


__all__ = ["diff_resource_revisions", "print_revision_diff", "list_repo_files"]
