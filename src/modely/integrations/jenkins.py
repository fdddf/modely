"""Jenkins integration adapter contract."""

from __future__ import annotations

from . import IntegrationCapability, planned_capability


def get_jenkins_capability() -> IntegrationCapability:
    """Return the planned Jenkins integration capability descriptor."""

    return planned_capability("Jenkins")


__all__ = ["get_jenkins_capability"]
