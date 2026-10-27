"""Training platform integration adapter contract."""

from __future__ import annotations

from . import IntegrationCapability, planned_capability


def get_training_platform_capability() -> IntegrationCapability:
    """Return the planned Training platform integration capability descriptor."""

    return planned_capability("Training platform")


__all__ = ["get_training_platform_capability"]
