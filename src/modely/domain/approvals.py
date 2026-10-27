"""Approval request domain objects.

This module defines the canonical ApprovalRequest entity and helper functions
used by governance, catalog, CLI, and future server flows.  The approval state
machine and invariants are defined here; lifecycle services that mutate or
evaluate requests live in ``modely.governance.approvals``.

The canonical approval_state enum values are:
    none       — No approval workflow applies or has been requested.
    pending    — A request is awaiting review.
    approved   — Use is approved within its scope and expiry.
    rejected   — Request was denied.
    expired    — Previous approval is no longer valid.
    cancelled  — Request was withdrawn or superseded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

# Re-export the canonical type alias from domain.policies so callers get one
# canonical definition regardless of whether they import from domain.policies
# or domain.approvals.
from ..domain.policies import ApprovalState, APPROVAL_STATES  # noqa: F401

# ---------------------------------------------------------------------------
# Break-glass constants
# ---------------------------------------------------------------------------

#: Time-to-live for break-glass overrides in hours.
BREAK_GLASS_DEFAULT_TTL_HOURS: int = 4

#: Minimum reason length for break-glass justification.
BREAK_GLASS_MIN_REASON_LENGTH: int = 50

#: Maximum principals on the break-glass allowlist.
BREAK_GLASS_MAX_ALLOWLIST_SIZE: int = 10

# ---------------------------------------------------------------------------
# SLA and expiry defaults
# ---------------------------------------------------------------------------

#: Default SLA target in hours for standard approval requests.
DEFAULT_SLA_HOURS: int = 24

#: Default SLA target in hours for high-risk approval requests.
HIGH_RISK_SLA_HOURS: int = 8

#: Default approval expiry in hours.
DEFAULT_APPROVAL_EXPIRY_HOURS: int = 168  # 7 days

#: Reminder interval in hours before SLA breach.
SLA_REMINDER_INTERVAL_HOURS: int = 4

# ---------------------------------------------------------------------------
# Approval state machine adjacency map
# ---------------------------------------------------------------------------

APPROVAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "none": frozenset({"pending"}),
    "pending": frozenset({"approved", "rejected", "cancelled", "expired"}),
    "approved": frozenset({"expired"}),
    "rejected": frozenset(),
    "cancelled": frozenset(),
    "expired": frozenset(),
}

# ---------------------------------------------------------------------------
# Canonical ApprovalRequest dataclass
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    """Canonical approval request entity for Phase 2+ governance flows.

    This is the shared approval DTO consumed by the catalog, governance
    services, CLI, and future API/sync workflows.  All state transitions
    MUST flow through ``transition_request`` which enforces the state
    machine declared in ``APPROVAL_TRANSITIONS``.
    """

    id: str
    asset_id: str
    requester_principal: str
    tenant_scope: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    requested_actions: list[str] = field(default_factory=list)
    state: ApprovalState = "none"
    reviewers: list[str] = field(default_factory=list)
    decision_by: Optional[str] = None
    decision_at: Optional[str] = None
    decision_reason: Optional[str] = None
    expires_at: Optional[str] = None
    policy_decision_ref: Optional[str] = None
    sla_target: Optional[str] = None
    notification_state: str = "pending"  # pending, sent, acknowledged, failed
    escalation_state: str = "none"  # none, level1, level2, emergency
    comments: list[dict[str, Any]] = field(default_factory=list)

    # ── backward-compatibility aliases ──────────────────────────────────────
    # Older callers use ``ApprovalRequest(id, asset_id, requester, ...)`` or
    # ``ApprovalRequest(id=..., asset_id=..., requester=..., status=...)``.
    # We intercept these in a custom __init__ and remap them to the canonical
    # field names.

    def __init__(
        self,
        id: str,
        asset_id: str,
        requester_principal: str = "",
        *,
        tenant_scope: Optional[dict[str, Any]] = None,
        reason: Optional[str] = None,
        requested_actions: Optional[list[str]] = None,
        state: ApprovalState = "none",
        reviewers: Optional[list[str]] = None,
        decision_by: Optional[str] = None,
        decision_at: Optional[str] = None,
        decision_reason: Optional[str] = None,
        expires_at: Optional[str] = None,
        policy_decision_ref: Optional[str] = None,
        sla_target: Optional[str] = None,
        notification_state: str = "pending",
        escalation_state: str = "none",
        comments: Optional[list[dict[str, Any]]] = None,
        # ── backward-compatibility kwargs ─────────────────────────────────
        requester: str = "",
        status: str = "",
    ) -> None:
        # Map backward-compat kwargs
        if requester and not requester_principal:
            requester_principal = requester
        if status and state == "none":
            state = status  # type: ignore[assignment]

        self.id = id
        self.asset_id = asset_id
        self.requester_principal = requester_principal
        self.tenant_scope = tenant_scope
        self.reason = reason
        self.requested_actions = requested_actions if requested_actions is not None else []
        self.state = state
        self.reviewers = reviewers if reviewers is not None else []
        self.decision_by = decision_by
        self.decision_at = decision_at
        self.decision_reason = decision_reason
        self.expires_at = expires_at
        self.policy_decision_ref = policy_decision_ref
        self.sla_target = sla_target
        self.notification_state = notification_state
        self.escalation_state = escalation_state
        self.comments = comments if comments is not None else []

        if self.state not in APPROVAL_STATES:
            raise ValueError(
                f"Invalid approval_state: {self.state!r}. "
                f"Must be one of {APPROVAL_STATES}."
            )

    @property
    def status(self) -> str:
        """Backward-compatibility alias for ``state``."""
        return self.state

    @status.setter
    def status(self, value: str) -> None:
        self.state = value  # type: ignore[assignment]

    @property
    def requester(self) -> str:
        """Backward-compatibility alias for ``requester_principal``."""
        return self.requester_principal

    @requester.setter
    def requester(self, value: str) -> None:
        self.requester_principal = value

    @property
    def reviewer(self) -> Optional[str]:
        """Backward-compatibility alias for ``decision_by``."""
        return self.decision_by

    @reviewer.setter
    def reviewer(self, value: Optional[str]) -> None:
        self.decision_by = value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_terminal(self) -> bool:
        """Return True if the request is in a terminal state."""
        return self.state in {"approved", "rejected", "expired", "cancelled"}

    def is_modifiable(self) -> bool:
        """Return True if the request can still be modified (not approved)."""
        return self.state != "approved"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_approval_state(value: str) -> bool:
    """Return whether *value* is a canonical approval state."""
    return value in APPROVAL_STATES


def can_transition_approval(current_state: str, target_state: str) -> bool:
    """Return whether a transition from *current_state* to *target_state* is valid."""
    allowed = APPROVAL_TRANSITIONS.get(current_state, frozenset())
    return target_state in allowed


def compute_sla_target(
    risk_level: str = "medium",
    *,
    sla_hours: int | None = None,
) -> str:
    """Compute an SLA target ISO-8601 timestamp from now.

    Args:
        risk_level: ``"low"``, ``"medium"``, ``"high"``, or ``"critical"``.
        sla_hours: Override the risk-based default.

    Returns:
        ISO-8601 UTC timestamp *sla_hours* from now.
    """
    hours = sla_hours or {
        "low": DEFAULT_SLA_HOURS * 2,
        "medium": DEFAULT_SLA_HOURS,
        "high": HIGH_RISK_SLA_HOURS,
        "critical": HIGH_RISK_SLA_HOURS // 2,
    }.get(risk_level, DEFAULT_SLA_HOURS)
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def compute_expiry(approval_hours: int = DEFAULT_APPROVAL_EXPIRY_HOURS) -> str:
    """Compute an approval expiry ISO-8601 timestamp from now.

    Args:
        approval_hours: Hours until the approval expires (default 168 = 7 days).

    Returns:
        ISO-8601 UTC timestamp.
    """
    return (datetime.now(timezone.utc) + timedelta(hours=approval_hours)).isoformat()


def compute_reminder_time(sla_target: str) -> str | None:
    """Compute the next reminder time before the SLA target.

    Args:
        sla_target: ISO-8601 UTC timestamp of the SLA target.

    Returns:
        ISO-8601 UTC timestamp of the reminder, or ``None`` if the SLA target
        is already past.
    """
    try:
        target = datetime.fromisoformat(sla_target.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    now = datetime.now(timezone.utc)
    reminder = target - timedelta(hours=SLA_REMINDER_INTERVAL_HOURS)
    if reminder <= now:
        return None
    return reminder.isoformat()


__all__ = [
    "APPROVAL_STATES",
    "APPROVAL_TRANSITIONS",
    "ApprovalRequest",
    "ApprovalState",
    "BREAK_GLASS_DEFAULT_TTL_HOURS",
    "BREAK_GLASS_MAX_ALLOWLIST_SIZE",
    "BREAK_GLASS_MIN_REASON_LENGTH",
    "DEFAULT_APPROVAL_EXPIRY_HOURS",
    "DEFAULT_SLA_HOURS",
    "HIGH_RISK_SLA_HOURS",
    "SLA_REMINDER_INTERVAL_HOURS",
    "can_transition_approval",
    "compute_expiry",
    "compute_reminder_time",
    "compute_sla_target",
    "is_approval_state",
]
