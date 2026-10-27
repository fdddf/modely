"""Sync job lifecycle and state transitions."""

from __future__ import annotations

SYNC_JOB_TRANSITIONS: dict[str, set[str]] = {
    "registered": {"planned", "syncing", "disabled", "failed"},
    "planned": {"syncing", "disabled", "failed"},
    "syncing": {"synced", "failed"},
    "synced": {"planned", "syncing", "disabled", "unchanged", "drifted"},
    "failed": {"planned", "syncing", "disabled"},
    "disabled": {"enabled"},
    "enabled": {"planned", "syncing", "disabled"},
    "unsupported": {"planned", "syncing", "disabled"},
    "unchanged": {"planned", "syncing", "disabled", "drifted"},
    "drifted": {"planned", "syncing", "disabled", "synced"},
}


def can_transition(current: str, next_status: str) -> bool:
    """Return whether a sync job state transition is allowed."""

    return next_status in SYNC_JOB_TRANSITIONS.get(current, set())


def transition_status(current: str, next_status: str) -> str:
    """Validate and return a sync job status transition."""

    if not can_transition(current, next_status):
        raise ValueError(f"Invalid sync transition: {current} -> {next_status}")
    return next_status


__all__ = ["SYNC_JOB_TRANSITIONS", "can_transition", "transition_status"]
