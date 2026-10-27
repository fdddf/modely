"""GitLab CI integration adapter contract."""

from __future__ import annotations

from . import IntegrationCapability, planned_capability


def get_gitlab_capability() -> IntegrationCapability:
    """Return the planned GitLab CI integration capability descriptor."""

    return planned_capability("GitLab CI")


__all__ = ["get_gitlab_capability"]
