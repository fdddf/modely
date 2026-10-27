"""Compatibility facade for asset health scoring helpers."""

from __future__ import annotations

from .intelligence.scoring import *  # noqa: F401,F403
from .intelligence.scoring import score_resource as _score_resource
from .intelligence.analysis import analyze_resource


def score_resource(*args, **kwargs):
    kwargs.setdefault("analyze_resource_func", analyze_resource)
    return _score_resource(*args, **kwargs)
