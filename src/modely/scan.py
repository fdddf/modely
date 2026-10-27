"""Compatibility facade for metadata-only asset risk scanning helpers."""

from __future__ import annotations

from .intelligence.scanning import *  # noqa: F401,F403
from .intelligence.scanning import scan_resource as _scan_resource
from .intelligence.analysis import analyze_resource


def scan_resource(*args, **kwargs):
    from . import intelligence

    kwargs.setdefault("analyze_resource_func", analyze_resource)
    return _scan_resource(*args, **kwargs)
