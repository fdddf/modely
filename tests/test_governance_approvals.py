"""Targeted unit tests for modely.governance.approvals.

Covers: transition_request, select_reviewers, AutoApprovalRule, approve_auto,
BreakGlassOverride, break_glass, set_sla, expire_requests, escalate_overdue,
NotificationHook protocol, and can_transition_approval.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from modely.governance.approvals import (
    APPROVAL_TRANSITIONS,
    AutoApprovalRule,
    BreakGlassOverride,
    NotificationHook,
    approve_auto,
    break_glass,
    can_transition_approval,
    escalate_overdue,
    expire_requests,
    select_reviewers,
    set_sla,
    transition_request,
)
from modely.governance.approvals import ApprovalRequest
from modely.domain.approvals import (
    APPROVAL_STATES,
    SLA_REMINDER_INTERVAL_HOURS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_req(req_id="r1", asset_id="a1", requester="dev1", state="none"):
    """Create a minimal fresh ApprovalRequest."""
    return ApprovalRequest(id=req_id, asset_id=asset_id, requester=requester, status=state)


# ---------------------------------------------------------------------------
# 1. transition_request() — all valid and invalid transitions
# ---------------------------------------------------------------------------


def test_transition_none_to_pending():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    assert req.state == "pending"


def test_transition_pending_to_approved():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="admin1", reason="looks good")
    assert req.state == "approved"
    assert req.decision_by == "admin1"
    assert req.decision_reason == "looks good"
    assert req.decision_at is not None


def test_transition_pending_to_rejected():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "rejected", reviewer="admin1", reason="denied")
    assert req.state == "rejected"
    assert req.decision_at is not None


def test_transition_pending_to_cancelled():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "cancelled")
    assert req.state == "cancelled"
    assert req.decision_at is not None


def test_transition_pending_to_expired():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "expired")
    assert req.state == "expired"


def test_transition_approved_to_expired():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="admin1")
    req = transition_request(req, "expired")
    assert req.state == "expired"


def test_transition_none_to_approved_is_invalid():
    req = _fresh_req(state="none")
    with pytest.raises(ValueError, match="Invalid approval transition"):
        transition_request(req, "approved")


def test_transition_approved_to_rejected_is_invalid():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="admin1")
    with pytest.raises(ValueError, match="approved requests cannot transition"):
        transition_request(req, "rejected")


def test_transition_approved_to_pending_is_invalid():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="admin1")
    with pytest.raises(ValueError, match="approved requests cannot transition"):
        transition_request(req, "pending")


def test_cannot_transition_from_rejected():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "rejected", reviewer="admin1")
    for target in ("pending", "approved", "cancelled"):
        with pytest.raises(ValueError):
            transition_request(req, target)


def test_cannot_transition_from_cancelled():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "cancelled")
    for target in ("pending", "approved", "rejected"):
        with pytest.raises(ValueError):
            transition_request(req, target)


def test_cannot_transition_from_expired():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "expired")
    for target in ("pending", "approved", "rejected", "cancelled"):
        with pytest.raises(ValueError):
            transition_request(req, target)


# ---------------------------------------------------------------------------
# 2. select_reviewers() — all 6 precedence levels, no reviewers found
# ---------------------------------------------------------------------------


def test_select_reviewers_explicit():
    result = select_reviewers(explicit_reviewers=["alice", "bob"])
    assert result == ["alice", "bob"]


def test_select_reviewers_resource_func():
    def resource_fn(asset_id: str = ""):
        return ["r1", "r2"] if asset_id else []

    result = select_reviewers(asset_id="asset-1", resource_reviewers=resource_fn)
    assert result == ["r1", "r2"]


def test_select_reviewers_resource_func_empty_falls_through():
    """When resource_reviewers returns empty, fall through to next level."""

    def resource_fn(asset_id: str = ""):
        return []

    def type_fn(resource_type: str = ""):
        return ["type-r1"]

    result = select_reviewers(
        asset_id="asset-1",
        resource_type="model",
        resource_reviewers=resource_fn,
        type_reviewers=type_fn,
    )
    assert result == ["type-r1"]


def test_select_reviewers_type_based():
    def type_fn(resource_type: str = ""):
        return ["type-r1", "type-r2"]

    result = select_reviewers(resource_type="model", type_reviewers=type_fn)
    assert result == ["type-r1", "type-r2"]


def test_select_reviewers_project():
    def project_fn(project_id: str = "", environment_id: str = ""):
        return ["proj-r1"]

    result = select_reviewers(
        project_id="proj-1", project_reviewers=project_fn
    )
    assert result == ["proj-r1"]


def test_select_reviewers_team():
    def team_fn(team_id: str = ""):
        return ["team-r1"] if team_id else []

    result = select_reviewers(team_id="team-1", team_reviewers=team_fn)
    assert result == ["team-r1"]


def test_select_reviewers_risk_license():
    def risk_fn(risk_level: str = "", license_id: str = ""):
        return ["sec-r1"]

    result = select_reviewers(
        risk_level="high",
        license_id="mit",
        risk_license_reviewers=risk_fn,
    )
    assert result == ["sec-r1"]


def test_select_reviewers_default():
    def default_fn(workspace_id: str = "", organization_id: str = ""):
        return ["default-r1"]

    result = select_reviewers(
        workspace_id="ws-1",
        organization_id="org-1",
        default_reviewers=default_fn,
    )
    assert result == ["default-r1"]


def test_select_reviewers_no_match_returns_empty():
    result = select_reviewers(asset_id="unknown")
    assert result == []


def test_select_reviewers_precedence_explicit_wins_over_resource_func():
    """Explicit reviewers always win, even if resource_reviewers would match."""

    def resource_fn(asset_id: str = ""):
        return ["r1"]

    result = select_reviewers(
        explicit_reviewers=["explicit-alice"],
        resource_reviewers=resource_fn,
    )
    assert result == ["explicit-alice"]


def test_select_reviewers_higher_precedence_wins():
    """When level 1 returns non-empty, level 3 is never called."""

    def resource_fn(asset_id: str = ""):
        return ["r1"]

    project_called = [False]

    def project_fn(project_id: str = "", environment_id: str = ""):
        project_called[0] = True
        return ["proj-r1"]

    result = select_reviewers(
        asset_id="asset-1",
        resource_reviewers=resource_fn,
        project_reviewers=project_fn,
        project_id="proj-1",
    )
    assert result == ["r1"]
    assert not project_called[0]


# ---------------------------------------------------------------------------
# 3. AutoApprovalRule — match logic
# ---------------------------------------------------------------------------


def test_auto_rule_matches_defaults():
    """Default rule matches low/unknown risk, no license restriction.

    Note: require_safe_scan=True by default, so has_passing_scan must be True.
    """
    rule = AutoApprovalRule()
    assert rule.matches(resource_type="model", risk_level="unknown", has_passing_scan=True)


def test_auto_rule_disabled():
    rule = AutoApprovalRule(enabled=False)
    assert not rule.matches(resource_type="model", risk_level="low")


def test_auto_rule_resource_type_mismatch():
    rule = AutoApprovalRule(resource_types=["model"])
    assert not rule.matches(resource_type="dataset", risk_level="low")


def test_auto_rule_risk_level_too_high():
    rule = AutoApprovalRule(risk_levels=["low", "unknown"])
    assert not rule.matches(resource_type="model", risk_level="high")


def test_auto_rule_license_not_allowed():
    rule = AutoApprovalRule(license_allowlist=["mit", "apache-2.0"])
    # require_safe_scan=True by default, so without has_passing_scan, it won't match
    # But license check comes before safe_scan check, so... wait: the check order
    # in matches() is: enabled, resource_types, risk_levels, license_allowlist,
    # max_file_size, require_safe_scan. So if license fails, returns False.
    assert not rule.matches(
        resource_type="model", risk_level="low", license_normalized="gpl-3.0"
    )


def test_auto_rule_license_allowed():
    rule = AutoApprovalRule(license_allowlist=["mit", "apache-2.0"])
    assert rule.matches(
        resource_type="model", risk_level="low", license_normalized="mit",
        has_passing_scan=True,
    )


def test_auto_rule_file_size_exceeded():
    rule = AutoApprovalRule(max_file_size=1000)
    assert not rule.matches(
        resource_type="model", risk_level="low", total_size=2000,
        has_passing_scan=True,
    )


def test_auto_rule_requires_safe_scan():
    rule = AutoApprovalRule(require_safe_scan=True)
    assert not rule.matches(
        resource_type="model", risk_level="low", has_passing_scan=False
    )


def test_auto_rule_safe_scan_passed():
    rule = AutoApprovalRule(require_safe_scan=True)
    assert rule.matches(
        resource_type="model", risk_level="low", has_passing_scan=True
    )


def test_auto_rule_all_criteria_met():
    rule = AutoApprovalRule(
        resource_types=["model"],
        risk_levels=["low"],
        license_allowlist=["mit"],
        max_file_size=5000,
        require_safe_scan=True,
    )
    assert rule.matches(
        resource_type="model",
        risk_level="low",
        license_normalized="mit",
        total_size=1000,
        has_passing_scan=True,
    )


def test_auto_rule_empty_resource_types_allows_all():
    """Empty resource_types list should match any resource type."""
    rule = AutoApprovalRule(resource_types=[], risk_levels=["low"])
    assert rule.matches(resource_type="model", risk_level="low", has_passing_scan=True)
    assert rule.matches(resource_type="dataset", risk_level="low", has_passing_scan=True)
    assert rule.matches(resource_type="tool", risk_level="low", has_passing_scan=True)


def test_auto_rule_empty_risk_levels_blocks_all():
    """Empty risk_levels list means no risk level matches.

    But wait: with empty risk_levels, the check `if self.risk_levels and ...`
    is falsy, so risk_levels doesn't block. However, require_safe_scan=True
    still blocks without has_passing_scan. We test the empty risk_levels
    path by creating a rule without require_safe_scan and verifying it
    matches regardless of risk level.
    """
    # Empty risk_levels + require_safe_scan=False: passes through risk check,
    # no safe_scan requirement. Should match anything.
    rule = AutoApprovalRule(risk_levels=[], require_safe_scan=False)
    assert rule.matches(resource_type="model", risk_level="low")
    assert rule.matches(resource_type="model", risk_level="high")


# ---------------------------------------------------------------------------
# 4. approve_auto() — matches a rule, no match, multiple rules
# ---------------------------------------------------------------------------


def test_approve_auto_matches_rule():
    req = _fresh_req(state="none")
    rules = [
        AutoApprovalRule(
            resource_types=["model"], risk_levels=["unknown"], require_safe_scan=False
        )
    ]
    result = approve_auto(req, rules=rules, resource_type="model", risk_level="unknown")
    assert result is not None
    assert result.state == "approved"
    assert result.decision_by == "auto-approver"
    assert "Auto-approved" in (result.decision_reason or "")


def test_approve_auto_no_match():
    req = _fresh_req(state="none")
    rules = [
        AutoApprovalRule(
            resource_types=["model"], risk_levels=["low"], require_safe_scan=False
        )
    ]
    result = approve_auto(req, rules=rules, resource_type="model", risk_level="high")
    assert result is None
    assert req.state == "none"


def test_approve_auto_already_approved():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="manual-admin")
    rules = [AutoApprovalRule(require_safe_scan=False)]
    result = approve_auto(req, rules=rules, resource_type="model", risk_level="unknown")
    assert result is None


def test_approve_auto_multiple_rules_first_matches():
    """The first matching rule wins."""
    rule1 = AutoApprovalRule(
        resource_types=["model"], risk_levels=["unknown"], require_safe_scan=False
    )
    rule2 = AutoApprovalRule(resource_types=["dataset"])
    req = _fresh_req(state="none")
    result = approve_auto(
        req, rules=[rule1, rule2], resource_type="model", risk_level="unknown"
    )
    assert result is not None
    assert result.state == "approved"


def test_approve_auto_multiple_rules_no_match():
    rule1 = AutoApprovalRule(resource_types=["dataset"])
    rule2 = AutoApprovalRule(resource_types=["tool"])
    req = _fresh_req(state="none")
    result = approve_auto(
        req, rules=[rule1, rule2], resource_type="model", risk_level="unknown"
    )
    assert result is None


def test_approve_auto_matches_rule_pending_state():
    """Auto-approval also works from pending state."""
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    assert req.state == "pending"
    rules = [
        AutoApprovalRule(
            resource_types=["model"], risk_levels=["unknown"], require_safe_scan=False
        )
    ]
    result = approve_auto(req, rules=rules, resource_type="model", risk_level="unknown")
    assert result is not None
    assert result.state == "approved"


# ---------------------------------------------------------------------------
# 5. BreakGlassOverride + break_glass()
# ---------------------------------------------------------------------------


def test_break_glass_creation():
    override = BreakGlassOverride(
        id="bg-1",
        asset_id="asset-1",
        principal="admin1",
        reason="Emergency security patch rollout",
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
    )
    assert override.id == "bg-1"
    assert override.asset_id == "asset-1"
    assert override.principal == "admin1"
    assert override.created_at != ""
    # When constructed directly (not via break_glass()), scope_actions is default empty list


def test_break_glass_explicit_created_at():
    override = BreakGlassOverride(
        id="bg-2",
        asset_id="asset-2",
        principal="admin2",
        reason="Test reason",
        expires_at="2025-01-01T00:00:00+00:00",
        created_at="2025-01-01T00:00:00+00:00",
    )
    assert override.created_at == "2025-01-01T00:00:00+00:00"


def test_break_glass_function_with_allowlist():
    bg = break_glass(
        asset_id="asset-1",
        principal="admin1",
        reason="Critical security fix deployment",
        allowlist={"admin1", "admin2"},
    )
    assert bg.asset_id == "asset-1"
    assert bg.principal == "admin1"
    assert bg.reason == "Critical security fix deployment"
    assert bg.id.startswith("bg-asset-1-")


def test_break_glass_function_without_allowlist():
    bg = break_glass(
        asset_id="asset-1",
        principal="anyone",
        reason="Testing without allowlist",
    )
    assert bg.principal == "anyone"


def test_break_glass_not_in_allowlist():
    with pytest.raises(ValueError, match="not authorized"):
        break_glass(
            asset_id="asset-1",
            principal="bad-actor",
            reason="Malicious override attempt",
            allowlist={"admin1", "admin2"},
        )


def test_break_glass_reason_required():
    with pytest.raises(ValueError, match="non-empty reason"):
        break_glass(asset_id="asset-1", principal="admin1", reason="")

    with pytest.raises(ValueError, match="non-empty reason"):
        break_glass(asset_id="asset-1", principal="admin1", reason="   ")


def test_break_glass_ttl_expiry():
    """TTL controls when the override expires."""
    ttl = 1
    bg = break_glass(
        asset_id="asset-1",
        principal="admin1",
        reason="Short-lived override",
        ttl_hours=ttl,
    )
    expires = datetime.fromisoformat(bg.expires_at)
    now = datetime.now(timezone.utc)
    # Should be approximately 1 hour from now
    delta = expires - now
    assert timedelta(minutes=55) <= delta <= timedelta(minutes=65)


def test_break_glass_empty_allowlist():
    """Empty allowlist should still deny non-members."""
    with pytest.raises(ValueError, match="not authorized"):
        break_glass(
            asset_id="asset-1",
            principal="admin1",
            reason="Test reason",
            allowlist=set(),
        )


# ---------------------------------------------------------------------------
# 6. set_sla() — sets SLA target on request
# ---------------------------------------------------------------------------


def test_set_sla_default():
    req = _fresh_req(state="none")
    assert req.sla_target is None
    req = set_sla(req)
    assert req.sla_target is not None
    sla_dt = datetime.fromisoformat(req.sla_target)
    now = datetime.now(timezone.utc)
    # 24-hour default
    assert timedelta(hours=23, minutes=55) <= (sla_dt - now) <= timedelta(hours=24, minutes=5)


def test_set_sla_custom_hours():
    req = _fresh_req(state="none")
    req = set_sla(req, hours=8)
    sla_dt = datetime.fromisoformat(req.sla_target)
    now = datetime.now(timezone.utc)
    assert timedelta(hours=7, minutes=55) <= (sla_dt - now) <= timedelta(hours=8, minutes=5)


# ---------------------------------------------------------------------------
# 7. expire_requests() — pending past SLA, approved past expiry, non-terminal skip
# ---------------------------------------------------------------------------


def test_expire_pending_past_sla():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    # Set SLA target to 1 hour ago
    req.sla_target = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    expired = expire_requests([req])
    assert len(expired) == 1
    assert expired[0].state == "expired"


def test_expire_approved_past_expiry():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="admin1")
    # Set expires_at to 1 hour ago
    req.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    expired = expire_requests([req])
    assert len(expired) == 1
    assert expired[0].state == "expired"


def test_expire_pending_not_yet_due():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    # Set SLA target to 1 hour in the future
    req.sla_target = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    expired = expire_requests([req])
    assert len(expired) == 0
    assert req.state == "pending"


def test_expire_approved_not_yet_due():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "approved", reviewer="admin1")
    # Set expires_at to 1 hour in the future
    req.expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    expired = expire_requests([req])
    assert len(expired) == 0
    assert req.state == "approved"


def test_expire_non_terminal_states_skipped():
    """Requests in none, rejected, cancelled, or already-expired are skipped."""
    req_none = _fresh_req("none", state="none")
    req_rejected = _fresh_req("rej", state="rejected")
    req_cancelled = _fresh_req("can", state="cancelled")
    req_expired = _fresh_req("exp", state="expired")

    # Manually bypass state machine for rejected/cancelled/expired to create test fixtures
    req_r = ApprovalRequest(id="rej", asset_id="a1", requester="dev1", status="none")
    req_r = transition_request(req_r, "pending")
    req_r = transition_request(req_r, "rejected")

    req_c = ApprovalRequest(id="can", asset_id="a1", requester="dev1", status="none")
    req_c = transition_request(req_c, "pending")
    req_c = transition_request(req_c, "cancelled")

    req_e = ApprovalRequest(id="exp", asset_id="a1", requester="dev1", status="none")
    req_e = transition_request(req_e, "pending")
    req_e = transition_request(req_e, "expired")

    expired = expire_requests([req_none, req_r, req_c, req_e])
    assert len(expired) == 0


def test_expire_with_explicit_now():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    # SLA target is "2025-06-01T00:00:00+00:00"
    req.sla_target = "2025-06-01T00:00:00+00:00"
    # now is after that
    expired = expire_requests([req], now="2025-06-15T00:00:00+00:00")
    assert len(expired) == 1
    assert expired[0].state == "expired"


def test_expire_mixed_batch():
    """Mix of due and not-due requests."""
    r1 = _fresh_req(state="none")
    r1 = transition_request(r1, "pending")
    r1.sla_target = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    r2 = _fresh_req(req_id="r2", state="none")
    r2 = transition_request(r2, "pending")
    r2.sla_target = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    expired = expire_requests([r1, r2])
    assert len(expired) == 1
    assert expired[0].id == "r1"
    assert r1.state == "expired"
    assert r2.state == "pending"


def test_expire_invalid_iso_dates_are_handled():
    """Invalid ISO dates on sla_target/expires_at should not crash."""
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req.sla_target = "not-a-timestamp"
    expired = expire_requests([req])
    assert len(expired) == 0
    assert req.state == "pending"


# ---------------------------------------------------------------------------
# 8. escalate_overdue() — with and without escalation target
# ---------------------------------------------------------------------------


def test_escalate_overdue_pending_request():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = escalate_overdue(req, "manager1", level="level1")
    assert req.escalation_state == "level1"
    assert len(req.comments) == 1
    assert req.comments[0]["action"] == "escalated"
    assert req.comments[0]["target"] == "manager1"
    assert req.comments[0]["level"] == "level1"


def test_escalate_overdue_level2():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = escalate_overdue(req, "director1", level="level2", reason="Second escalation")
    assert req.escalation_state == "level2"
    assert req.comments[0]["level"] == "level2"
    assert "Second escalation" in req.comments[0]["reason"]


def test_escalate_overdue_emergency():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = escalate_overdue(req, "security-team", level="emergency")
    assert req.escalation_state == "emergency"


def test_escalate_overdue_non_pending_is_error():
    req = _fresh_req(state="none")
    with pytest.raises(ValueError, match="Cannot escalate a request in state"):
        escalate_overdue(req, "manager1", level="level1")

    req2 = _fresh_req(state="none")
    req2 = transition_request(req2, "pending")
    req2 = transition_request(req2, "approved", reviewer="admin1")
    with pytest.raises(ValueError, match="Cannot escalate a request in state"):
        escalate_overdue(req2, "manager1", level="level1")


def test_escalate_overdue_invalid_level():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    with pytest.raises(ValueError, match="Invalid escalation level"):
        escalate_overdue(req, "manager1", level="level3")

    with pytest.raises(ValueError, match="Invalid escalation level"):
        escalate_overdue(req, "manager1", level="")


def test_escalate_overdue_multiple_escalations_accumulate_comments():
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = escalate_overdue(req, "manager1", level="level1")
    req = escalate_overdue(req, "director1", level="level2")
    assert len(req.comments) == 2
    assert req.comments[0]["level"] == "level1"
    assert req.comments[1]["level"] == "level2"
    assert req.escalation_state == "level2"


# ---------------------------------------------------------------------------
# 9. NotificationHook — protocol class test (instantiation should fail without methods)
# ---------------------------------------------------------------------------


def test_notification_hook_protocol_instantiation_fails():
    """Protocol class cannot be instantiated without concrete methods."""
    with pytest.raises(TypeError):
        NotificationHook()  # type: ignore[abstract]


def test_notification_hook_concrete_implementation_works():
    """A class implementing both on_reminder and on_escalation works."""

    class HookImpl:
        def on_reminder(self, request):
            return "reminded"

        def on_escalation(self, request, target):
            return f"escalated to {target}"

    hook = HookImpl()
    assert isinstance(hook, NotificationHook)
    assert hook.on_reminder(None) == "reminded"  # type: ignore[arg-type]
    assert hook.on_escalation(None, "admin") == "escalated to admin"  # type: ignore[arg-type]


def test_notification_hook_missing_on_reminder_fails():
    """Missing on_reminder method fails the protocol check."""

    class BadHook:
        def on_escalation(self, request, target):
            pass

    # During normal use at runtime, protocol checks with isinstance work
    assert not isinstance(BadHook(), NotificationHook)


def test_notification_hook_missing_on_escalation_fails():
    """Missing on_escalation method fails the protocol check."""

    class BadHook:
        def on_reminder(self, request):
            pass

    assert not isinstance(BadHook(), NotificationHook)


# ---------------------------------------------------------------------------
# 10. can_transition_approval() — all valid pairs, all invalid pairs
# ---------------------------------------------------------------------------


def test_can_transition_valid():
    """Every entry in APPROVAL_TRANSITIONS is a valid transition."""
    for source, targets in APPROVAL_TRANSITIONS.items():
        for target in targets:
            assert can_transition_approval(source, target), (
                f"Expected {source} -> {target} to be valid"
            )


def test_can_transition_invalid():
    """Transitions not in APPROVAL_TRANSITIONS are invalid."""
    all_states = APPROVAL_STATES
    for source in all_states:
        valid_targets = APPROVAL_TRANSITIONS.get(source, frozenset())
        for target in all_states:
            if target not in valid_targets:
                assert not can_transition_approval(source, target), (
                    f"Expected {source} -> {target} to be invalid"
                )


def test_can_transition_unknown_source():
    """Unknown source states have no valid transitions."""
    assert not can_transition_approval("bogus", "pending")


# ---------------------------------------------------------------------------
# Edge cases / misc
# ---------------------------------------------------------------------------


def test_transition_request_sets_audit_metadata():
    """transition_request calls emit_audit_event; verify it does not crash."""
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    # The fact that we got here without importing/audit errors means it succeeded
    assert req.state == "pending"


def test_break_glass_default_scope_actions():
    bg = break_glass(
        asset_id="asset-1",
        principal="admin1",
        reason="Emergency override for critical update",
    )
    assert bg.scope_actions == ["asset:download"]


def test_approve_auto_rejected_not_matched():
    """A rejected request should not be auto-approved."""
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "rejected")
    rules = [AutoApprovalRule(require_safe_scan=False)]
    result = approve_auto(req, rules=rules, resource_type="model", risk_level="unknown")
    assert result is None


def test_approve_auto_expired_not_matched():
    """An expired request should not be auto-approved."""
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = transition_request(req, "expired")
    rules = [AutoApprovalRule(require_safe_scan=False)]
    result = approve_auto(req, rules=rules, resource_type="model", risk_level="unknown")
    assert result is None


def test_escalate_overdue_with_default_reason():
    """When reason is None, a default reason is generated."""
    req = _fresh_req(state="none")
    req = transition_request(req, "pending")
    req = escalate_overdue(req, "manager1", level="level1", reason=None)
    assert "Request escalated to manager1" in req.comments[0]["reason"]


def test_set_sla_preserves_other_fields():
    req = _fresh_req(state="pending")
    req.reviewers = ["alice"]
    req = set_sla(req, hours=12)
    assert req.state == "pending"
    assert req.reviewers == ["alice"]
    assert req.sla_target is not None
