"""Compatibility facade for mirror verification helpers."""

from __future__ import annotations

from .compare import compare_resources
from .reproducibility.mirror import verify_mirror as _verify_mirror, print_mirror_verification


def verify_mirror(*args, **kwargs):
    kwargs.setdefault("compare_resources_func", compare_resources)
    return _verify_mirror(*args, **kwargs)


__all__ = ["verify_mirror", "print_mirror_verification", "compare_resources"]
