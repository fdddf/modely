"""Compatibility facade for cross-resource comparison helpers."""

from __future__ import annotations

from .intelligence.analysis import analyze_resource
from .reproducibility.comparison import *  # noqa: F401,F403
from .reproducibility.comparison import compare_resources as _compare_resources


def compare_resources(*args, **kwargs):
    kwargs.setdefault("analyze_resource_func", analyze_resource)
    return _compare_resources(*args, **kwargs)
