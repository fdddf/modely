"""Compatibility facade for asset analysis helpers."""

from __future__ import annotations

from .cataloging.cards import get_card
from .application.file_queries import classify_file, filter_files, format_file_size, list_repo_files, summarize_files
from .application.repo_queries import get_repo_info, resolve_repo_ref
from .application.download_profiles import resolve_download_profile
from .intelligence.analysis import analyze_resource as _analyze_resource, deep_file_analysis, print_asset_analysis
from .intelligence.analysis import _file_format, _is_dataset_file, _is_weight_file, _quantization_hint, _recommended_profiles, _risk_flags, _weight_formats


def analyze_resource(*args, **kwargs):
    kwargs.setdefault("get_repo_info_func", get_repo_info)
    kwargs.setdefault("list_repo_files_func", list_repo_files)
    kwargs.setdefault("get_card_func", get_card)
    return _analyze_resource(*args, **kwargs)


__all__ = [
    "analyze_resource",
    "deep_file_analysis",
    "print_asset_analysis",
    "get_repo_info",
    "list_repo_files",
    "get_card",
]
