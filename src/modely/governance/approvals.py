"""Usage approval lifecycle services.

This module provides the approval state machine, reviewer selection, auto-approval
rules, break-glass override, SLA tracking, escalation, notification hooks, and
expiry processing for Phase 2 governance flows.

The canonical ``ApprovalRequest`` entity lives in ``modely.domain.approvals``.
This module exposes compatibility aliases so existing callers that import from
``modely.governance.approvals`` continue to work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, Protocol, Sequence, runtime_checkable

# Re-export canonical domain objects for backward compatibility.
from ..domain.approvals import (
    APPROVAL_STATES,
    APPROVAL_TRANSITIONS,
    ApprovalRequest,
    can_transition_approval,
    is_approval_state,
)

__all__ = [
    "APPROVAL_STATES",
    "APPROVAL_TRANSITIONS",
    "ApprovalRequest",
    "AutoApprovalRule",
    "BreakGlassOverride",
    "NotificationHook",
    "approve_auto",
    "break_glass",
    "can_transition_approval",
    "escalate_overdue",
    "expire_requests",
    "is_approval_state",
    "select_reviewers",
    "set_sla",
    "transition_request",
]


# ---------------------------------------------------------------------------
# State transition (thin wrapper around domain-level state machine)
# ---------------------------------------------------------------------------


def transition_request(
    request: ApprovalRequest,
    status: str,
    *,
    reviewer: str | None = None,
    reason: str | None = None,
) -> ApprovalRequest:
    """Return *request* after applying a valid approval state transition.

    Invariants:
    - ``approved`` requests cannot be modified (except via ``expired``).
    - transitions that are not in ``APPROVAL_TRANSITIONS`` raise ``ValueError``.
    """

    if request.state == "approved" and status != "expired":
        raise ValueError(
            f"Invalid approval transition: approved requests cannot transition to {status!r}. "
            f"Only 'expired' is allowed from 'approved'."
        )

    if not can_transition_approval(request.state, status):
        raise ValueError(
            f"Invalid approval transition: {request.state} -> {status}"
        )

    previous_state = request.state
    request.state = status  # type: ignore[assignment]

    if reviewer is not None:
        request.decision_by = reviewer
    if reason is not None:
        request.decision_reason = reason

    if status in {"approved", "rejected", "cancelled"}:
        request.decision_at = datetime.now(timezone.utc).isoformat()

    # ── Audit: approval.{status} ──────────────────────────────────────────
    from .audit import emit_audit_event

    _APPROVAL_AUDIT_ACTIONS: dict[str, str] = {
        "requested": "approval.requested",
        "pending": "approval.requested",
        "approved": "approval.approved",
        "rejected": "approval.rejected",
        "cancelled": "approval.cancelled",
        "expired": "approval.expired",
    }
    audit_action = _APPROVAL_AUDIT_ACTIONS.get(status, f"approval.{status}")

    _ok_states = {"pending", "approved"}
    emit_audit_event(
        audit_action,
        resource=request.asset_id,
        status="ok" if status in _ok_states else "denied",
        actor=reviewer or request.requester_principal,
        metadata={
            "request_id": request.id,
            "from_state": previous_state,
            "to_state": status,
            "reason": request.decision_reason,
        },
        tenant_scope=(
            request.tenant_scope
            if isinstance(request.tenant_scope, dict)
            else (
                request.tenant_scope.to_dict()
                if hasattr(request.tenant_scope, "to_dict")
                else None
            )
        ),
    )

    return request


# ---------------------------------------------------------------------------
# Reviewer selection (6-level precedence)
# ---------------------------------------------------------------------------

_ReviewerLookupFn = Callable[
    ..., Sequence[str]
]  # (context) -> list of principal ids


def select_reviewers(
    *,
    asset_id: str = "",
    resource_type: str = "",
    project_id: str = "",
    environment_id: str = "",
    team_id: str = "",
    risk_level: str = "unknown",
    license_id: str = "",
    workspace_id: str = "",
    organization_id: str = "",
    explicit_reviewers: Sequence[str] = (),
    resource_reviewers: Optional[_ReviewerLookupFn] = None,
    type_reviewers: Optional[_ReviewerLookupFn] = None,
    project_reviewers: Optional[_ReviewerLookupFn] = None,
    team_reviewers: Optional[_ReviewerLookupFn] = None,
    risk_license_reviewers: Optional[_ReviewerLookupFn] = None,
    default_reviewers: Optional[_ReviewerLookupFn] = None,
) -> list[str]:
    """Select reviewers for an approval request using 6-level precedence.

    Precedence (highest first):

    1. **Explicit resource reviewers** — passed via *explicit_reviewers* or
       looked up via *resource_reviewers* for this specific *asset_id*.
    2. **Resource type-based reviewers** — looked up via *type_reviewers* for
       the given *resource_type* (e.g. model, dataset, tool).
    3. **Project/environment reviewers** — looked up via *project_reviewers*
       for *project_id* / *environment_id*.
    4. **Team reviewers** — looked up via *team_reviewers* for *team_id*.
    5. **Risk/license reviewers** — looked up via *risk_license_reviewers* for
       *risk_level* / *license_id*.
    6. **Workspace/org default** — looked up via *default_reviewers* for
       *workspace_id* / *organization_id*.

    Returns a (possibly empty) list of reviewer principal ids.  When a lookup
    function at a higher precedence level returns a non-empty result, lower
    precedence levels are skipped.
    """

    # 1. Explicit resource reviewers
    if explicit_reviewers:
        return list(explicit_reviewers)
    if resource_reviewers is not None:
        result = list(resource_reviewers(asset_id=asset_id))
        if result:
            return result

    # 2. Resource type-based reviewers
    if type_reviewers is not None and resource_type:
        result = list(type_reviewers(resource_type=resource_type))
        if result:
            return result

    # 3. Project/environment reviewers
    if project_reviewers is not None and (project_id or environment_id):
        result = list(
            project_reviewers(project_id=project_id, environment_id=environment_id)
        )
        if result:
            return result

    # 4. Team reviewers
    if team_reviewers is not None and team_id:
        result = list(team_reviewers(team_id=team_id))
        if result:
            return result

    # 5. Risk/license reviewers
    if risk_license_reviewers is not None and (risk_level or license_id):
        result = list(
            risk_license_reviewers(risk_level=risk_level, license_id=license_id)
        )
        if result:
            return result

    # 6. Workspace/org default
    if default_reviewers is not None and (workspace_id or organization_id):
        result = list(
            default_reviewers(
                workspace_id=workspace_id, organization_id=organization_id
            )
        )
        if result:
            return result

    return []


# ---------------------------------------------------------------------------
# Auto-approval rules
# ---------------------------------------------------------------------------


@dataclass
class AutoApprovalRule:
    """A rule that can automatically approve certain requests.

    Only applies to requests that would otherwise require manual review.
    Auto-approved requests still go through the state machine (none -> pending
    -> approved) for audit trail purposes.
    """

    resource_types: list[str] = field(default_factory=list)  # model, dataset, tool
    risk_levels: list[str] = field(
        default_factory=lambda: ["unknown", "low"]
    )  # max allowed risk
    license_allowlist: list[str] = field(default_factory=list)  # e.g. ["mit", "apache-2.0"]
    max_file_size: int = 0  # 0 = no limit
    require_safe_scan: bool = True  # must have passing scan
    enabled: bool = True

    def matches(
        self,
        *,
        resource_type: str,
        risk_level: str,
        license_normalized: str = "",
        file_count: int = 0,
        total_size: int = 0,
        has_passing_scan: bool = False,
    ) -> bool:
        """Return True if this rule matches the request context."""
        if not self.enabled:
            return False

        if self.resource_types and resource_type not in self.resource_types:
            return False

        if self.risk_levels and risk_level not in self.risk_levels:
            return False

        if self.license_allowlist and license_normalized not in self.license_allowlist:
            return False

        if self.max_file_size > 0 and total_size > self.max_file_size:
            return False

        if self.require_safe_scan and not has_passing_scan:
            return False

        return True


def approve_auto(
    request: ApprovalRequest,
    *,
    rules: Sequence[AutoApprovalRule],
    resource_type: str = "model",
    risk_level: str = "unknown",
    license_normalized: str = "",
    file_count: int = 0,
    total_size: int = 0,
    has_passing_scan: bool = False,
    reviewer: str = "auto-approver",
) -> ApprovalRequest | None:
    """Attempt to auto-approve *request* if any rule matches.

    Auto-approval only applies to requests in the ``none`` or ``pending`` state.
    Returns the updated request if auto-approved, or ``None`` if no rule matched.

    The caller is responsible for recording an audit event.
    """
    if request.state not in {"none", "pending"}:
        return None

    for rule in rules:
        if rule.matches(
            resource_type=resource_type,
            risk_level=risk_level,
            license_normalized=license_normalized,
            file_count=file_count,
            total_size=total_size,
            has_passing_scan=has_passing_scan,
        ):
            if request.state == "none":
                request = transition_request(request, "pending")
            request = transition_request(
                request, "approved",
                reviewer=reviewer,
                reason=f"Auto-approved by rule: {resource_type} / {risk_level} risk",
            )
            return request

    return None


# ---------------------------------------------------------------------------
# Break-glass override
# ---------------------------------------------------------------------------


@dataclass
class BreakGlassOverride:
    """A break-glass event that allows overriding a ``block`` decision.

    Break-glass is a constrained emergency override with mandatory audit trail.

    Constraints:
    - Only principals in an explicit allowlist may initiate a break-glass.
    - A reason is required.
    - The override expires quickly (default 24 hours).
    - An audit event MUST be recorded.
    """

    id: str
    asset_id: str
    principal: str
    reason: str
    expires_at: str
    created_at: str = ""
    scope_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


def break_glass(
    *,
    asset_id: str,
    principal: str,
    reason: str,
    allowlist: set[str] | None = None,
    ttl_hours: int = 24,
) -> BreakGlassOverride:
    """Create a break-glass override event.

    Args:
        asset_id: The blocked asset identifier.
        principal: The requesting principal.
        reason: A mandatory human-readable reason.
        allowlist: Principals allowed to use break-glass. If None, any
            principal can trigger break-glass (not recommended for production).
        ttl_hours: Hours until the override expires.

    Returns:
        A ``BreakGlassOverride`` instance.

    Raises:
        ValueError: If *principal* is not in *allowlist* or *reason* is empty.
    """
    if allowlist is not None and principal not in allowlist:
        raise ValueError(
            f"Principal {principal!r} is not authorized for break-glass override."
        )
    if not reason.strip():
        raise ValueError("Break-glass override requires a non-empty reason.")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    return BreakGlassOverride(
        id=f"bg-{asset_id}-{int(datetime.now(timezone.utc).timestamp())}",
        asset_id=asset_id,
        principal=principal,
        reason=reason.strip(),
        expires_at=expires_at.isoformat(),
        scope_actions=["asset:download"],
    )


# ---------------------------------------------------------------------------
# SLA tracking and expiry
# ---------------------------------------------------------------------------

_DEFAULT_SLA_HOURS = 24  # 24-hour SLA for approval review


def set_sla(request: ApprovalRequest, hours: int = _DEFAULT_SLA_HOURS) -> ApprovalRequest:
    """Set the SLA target on an approval request."""
    request.sla_target = (
        datetime.now(timezone.utc) + timedelta(hours=hours)
    ).isoformat()
    return request


def expire_requests(
    requests: Sequence[ApprovalRequest],
    *,
    now: str | None = None,
) -> list[ApprovalRequest]:
    """Check and expire approval requests that have passed their SLA or expiry.

    A pending request exceeding its ``sla_target`` transitions to ``expired``.
    An approved request exceeding its ``expires_at`` transitions to ``expired``.

    Returns the list of requests that were transitioned to ``expired``.
    """
    if now is None:
        now_dt = datetime.now(timezone.utc)
    else:
        now_dt = datetime.fromisoformat(now)

    expired: list[ApprovalRequest] = []

    for req in requests:
        if req.state == "pending" and req.sla_target:
            try:
                sla_dt = datetime.fromisoformat(req.sla_target)
                if now_dt > sla_dt:
                    transition_request(
                        req, "expired", reason="SLA timeout — request auto-expired"
                    )
                    expired.append(req)
            except (ValueError, TypeError):
                pass

        elif req.state == "approved" and req.expires_at:
            try:
                exp_dt = datetime.fromisoformat(req.expires_at)
                if now_dt > exp_dt:
                    transition_request(
                        req, "expired", reason="Approval validity period expired"
                    )
                    expired.append(req)
            except (ValueError, TypeError):
                pass

    return expired


# ---------------------------------------------------------------------------
# Notification hooks (reminder and escalation callbacks)
# ---------------------------------------------------------------------------


@runtime_checkable
class NotificationHook(Protocol):
    """Protocol for approval notification callbacks.

    Implementations handle delivery (email, webhook, Slack, etc.) as a
    deployment concern.  The governance layer calls these hooks and records
    audit events; it does NOT contain delivery logic.

    .. code-block:: python

        class EmailNotificationHook:
            def on_reminder(self, request: ApprovalRequest) -> None:
                send_email(request.reviewers, subject="Approval reminder: ...")

            def on_escalation(self, request: ApprovalRequest, target: str) -> None:
                send_email(target, subject="Approval escalated: ...")

        expire_requests(requests, hooks=EmailNotificationHook())

    Safety invariant:
        ``on_escalation`` MUST NOT auto-approve a high-risk resource.
        Escalation is about notification, not authorization.
    """

    def on_reminder(self, request: ApprovalRequest) -> None:
        """Called when a reminder threshold is reached before SLA breach.

        Args:
            request: The approval request nearing its SLA target.
        """
        ...

    def on_escalation(self, request: ApprovalRequest, target: str) -> None:
        """Called when SLA has been breached and escalation is triggered.

        Args:
            request: The overdue approval request.
            target: The escalation target (principal id, team id, or role).

        Safety:
            This method MUST NOT call ``transition_request(..., "approved")``.
            Escalation moves the approval to a reviewer, not to an approval.
        """
        ...


def _check_reminder(request: ApprovalRequest, *, now_dt: datetime, hooks: NotificationHook | None = None) -> None:
    """Check whether a pending request has reached its reminder time.

    Args:
        request: A pending approval request with an ``sla_target``.
        now_dt: Current datetime for comparison.
        hooks: Optional notification hook to call ``on_reminder``.
    """
    if hooks is None:
        return
    if request.state != "pending":
        return
    if not request.sla_target:
        return

    try:
        sla_dt = datetime.fromisoformat(request.sla_target.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return

    from ..domain.approvals import SLA_REMINDER_INTERVAL_HOURS

    threshold = sla_dt - timedelta(hours=SLA_REMINDER_INTERVAL_HOURS)
    if now_dt >= threshold and now_dt < sla_dt:
        # Only fire reminder once per notification_state cycle
        if request.notification_state == "pending":
            request.notification_state = "sent"
            hooks.on_reminder(request)


def escalate_overdue(
    request: ApprovalRequest,
    escalation_target: str,
    *,
    reason: str | None = None,
    level: str = "level1",
) -> ApprovalRequest:
    """Escalate an overdue approval request to the given target.

    Records an ``approval.escalated`` audit event and updates the request's
    escalation metadata.

    Args:
        request: A pending approval request past its SLA target.
        escalation_target: Principal, team, or role identifier receiving
            the escalation.  MUST NOT be used as an implicit approver.
        reason: Optional human-readable escalation reason.
        level: Escalation level — one of ``"level1"``, ``"level2"``,
            ``"emergency"``.

    Returns:
        The updated ``ApprovalRequest``.

    Raises:
        ValueError: If *level* is not a valid escalation level.

    Safety invariant:
        Escalation NEVER auto-approves.  This function updates metadata
        and records an audit event; it does NOT call ``transition_request``
        with ``"approved"``.  High-risk resources MUST remain pending
        until an authorized reviewer explicitly approves them.
    """
    _VALID_LEVELS = frozenset({"level1", "level2", "emergency"})
    if level not in _VALID_LEVELS:
        raise ValueError(
            f"Invalid escalation level: {level!r}. Must be one of {sorted(_VALID_LEVELS)}."
        )

    # ── Safety assertion: NEVER auto-approve ─────────────────────────────
    if request.state != "pending":
        raise ValueError(
            f"Cannot escalate a request in state {request.state!r}. "
            "Escalation is only applicable to pending requests."
        )

    request.escalation_state = level

    comment = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": "escalated",
        "level": level,
        "target": escalation_target,
        "reason": reason or f"Request escalated to {escalation_target} (level={level})",
    }
    request.comments.append(comment)

    # ── Record escalation in request metadata ────────────────────────────
    request._escalation_target = escalation_target  # type: ignore[attr-defined]

    # ── Audit: approval.escalated ────────────────────────────────────────
    from .audit import emit_audit_event

    emit_audit_event(
        "approval.escalated",
        resource=request.asset_id,
        status="ok",
        actor=request.requester_principal,
        metadata={
            "request_id": request.id,
            "escalation_level": level,
            "escalation_target": escalation_target,
            "reason": comment["reason"],
            "previous_escalation_state": request.escalation_state
            if not comment
            else "none",
        },
        tenant_scope=(
            request.tenant_scope
            if isinstance(request.tenant_scope, dict)
            else (
                request.tenant_scope.to_dict()
                if hasattr(request.tenant_scope, "to_dict")
                else None
            )
        ),
    )

    return request


# ── Update expire_requests to accept hooks and trigger reminders ────────────
# We override the existing expire_requests to integrate reminder checks and
# escalation notifications while preserving the original expiry logic and
# backwards compatibility.


def _original_expire_requests(
    requests: Sequence[ApprovalRequest],
    *,
    now: str | None = None,
    hooks: NotificationHook | None = None,
) -> list[ApprovalRequest]:
    """Check and expire approval requests that have passed their SLA or expiry.

    A pending request exceeding its ``sla_target`` transitions to ``expired``.
    An approved request exceeding its ``expires_at`` transitions to ``expired``.

    Also checks reminder thresholds when *hooks* is provided, and calls
    ``hooks.on_reminder`` for requests that have reached their reminder time
    but not yet the SLA target.

    Returns the list of requests that were transitioned to ``expired``.
    """
    if now is None:
        now_dt = datetime.now(timezone.utc)
    else:
        now_dt = datetime.fromisoformat(now)

    expired: list[ApprovalRequest] = []

    for req in requests:
        # ── Reminder check (before expiry) ────────────────────────────────
        _check_reminder(req, now_dt=now_dt, hooks=hooks)

        if req.state == "pending" and req.sla_target:
            try:
                sla_dt = datetime.fromisoformat(req.sla_target)
                if now_dt > sla_dt:
                    transition_request(
                        req, "expired", reason="SLA timeout — request auto-expired"
                    )
                    expired.append(req)
            except (ValueError, TypeError):
                pass

        elif req.state == "approved" and req.expires_at:
            try:
                exp_dt = datetime.fromisoformat(req.expires_at)
                if now_dt > exp_dt:
                    transition_request(
                        req, "expired", reason="Approval validity period expired"
                    )
                    expired.append(req)
            except (ValueError, TypeError):
                pass

    return expired


# Replace original expire_requests with enhanced version that supports hooks
expire_requests = _original_expire_requests
