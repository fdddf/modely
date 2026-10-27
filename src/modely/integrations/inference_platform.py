"""Inference platform integration adapter contract."""

from __future__ import annotations

from . import IntegrationCapability, planned_capability


def get_inference_platform_capability() -> IntegrationCapability:
    """Return the planned Inference platform integration capability descriptor."""

    return planned_capability("Inference platform")


__all__ = ["get_inference_platform_capability"]
