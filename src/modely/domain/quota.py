"""Quota domain objects for usage limits and enforcement.

Quota objects track limits on resources (downloads, storage, sync jobs, etc.)
for subjects (users, teams, organizations) and support advisory, soft-limit,
and hard-limit modes with configurable enforcement points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

QUOTA_MODES: tuple[str, ...] = ("advisory", "soft", "hard")
QUOTA_DIMENSIONS: tuple[str, ...] = (
    "storage",
    "downloads",
    "api_calls",
    "sync_jobs",
    "concurrent_tasks",
    "high_risk_requests",
)
QUOTA_ENFORCEMENT_POINTS: tuple[str, ...] = (
    "catalog_ingress",
    "download_egress",
    "api_gateway",
    "sync_scheduler",
    "worker_pool",
    "approval_gate",
)


@dataclass
class Quota:
    """A quota limit for a subject on a specific resource dimension.

    Enforcement points determine where the quota check is performed.
    """

    subject: str  # e.g. "user:u1", "team:t1", "org:org1"
    dimension: str  # e.g. "storage", "downloads", "api_calls"
    mode: str = "advisory"  # advisory (log only), soft (warn), hard (enforce)
    enforcement_points: list[str] = field(default_factory=list)
    limit: int = 0
    usage: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.dimension not in QUOTA_DIMENSIONS:
            raise ValueError(f"Unsupported quota dimension: {self.dimension}")
        if self.mode not in QUOTA_MODES:
            raise ValueError(f"Unsupported quota mode: {self.mode}")
        for point in self.enforcement_points:
            if point not in QUOTA_ENFORCEMENT_POINTS:
                raise ValueError(f"Unsupported enforcement point: {point}")

    @property
    def remaining(self) -> int:
        """Remaining capacity before hitting the limit."""
        return max(0, self.limit - self.usage)

    @property
    def exceeded(self) -> bool:
        """Whether current usage equals or exceeds the limit."""
        return self.usage >= self.limit


def check_quota(quota: Quota, requested: int) -> bool:
    """Check if a requested amount fits within the remaining quota.

    Returns ``True`` if the request is allowed (under limit or advisory/soft mode),
    ``False`` if it would exceed a hard limit.

    - advisory: always True (log only)
    - soft: always True (warn only)
    - hard: False if usage + requested >= limit
    """
    if quota.mode in ("advisory", "soft"):
        return True
    return (quota.usage + requested) < quota.limit


def check_quota_usage(quota: Quota) -> dict[str, Any]:
    """Return a structured quota usage report.

    Includes current usage, limit, remaining, exceeded flag, mode, and
    enforcement points.
    """
    return {
        "subject": quota.subject,
        "dimension": quota.dimension,
        "mode": quota.mode,
        "enforcement_points": list(quota.enforcement_points),
        "limit": quota.limit,
        "usage": quota.usage,
        "remaining": quota.remaining,
        "exceeded": quota.exceeded,
    }


__all__ = [
    "QUOTA_DIMENSIONS",
    "QUOTA_ENFORCEMENT_POINTS",
    "QUOTA_MODES",
    "Quota",
    "check_quota",
    "check_quota_usage",
]
