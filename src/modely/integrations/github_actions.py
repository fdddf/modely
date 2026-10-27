"""GitHub Actions integration adapter contract."""

from __future__ import annotations

from . import IntegrationCapability, planned_capability


def get_github_actions_capability() -> IntegrationCapability:
    """Return the planned GitHub Actions integration capability descriptor."""

    return planned_capability("GitHub Actions")


__all__ = ["get_github_actions_capability"]
