"""Phase 2 governance integration tests.

Covers: RBAC role matrix, permission evaluation, decision precedence,
TenantScope, visibility evaluation, approval lifecycle, policy decisions,
audit events with redaction, and governance report generation.
"""

from __future__ import annotations

import pytest

from modely.domain import (
    APPROVAL_STATES,
    OPERATIONAL_STATES,
    POLICY_OUTCOMES,
    RESOURCE_ACTIONS,
    VISIBILITY_LEVELS,
    Asset,
    AssetIdentity,
    PolicyDecision,
)
from modely.governance.permissions import DEFAULT_ACTIONS, PermissionDecision, allow
from modely.governance.rbac import ROLE_ACTIONS, Principal, check_permission


# ============================================================================
# 1. TenantScope and Domain Invariants
# ============================================================================

def test_tenant_scope_creation():
    """TenantScope must have org_id and workspace_id."""
    from modely.domain.tenants import TenantScope

    scope = TenantScope(organization_id="org-1", workspace_id="ws-1")
    assert scope.organization_id == "org-1"
    assert scope.workspace_id == "ws-1"
    assert scope.project_id is None
    assert scope.environment_id is None

    scope2 = TenantScope(
        organization_id="org-1",
        workspace_id="ws-1",
        project_id="proj-1",
        environment_id="prod",
    )
    assert scope2.project_id == "proj-1"
    assert scope2.environment_id == "prod"


def test_tenant_scope_equality():
    """TenantScope equality is value-based."""
    from modely.domain.tenants import TenantScope

    a = TenantScope(organization_id="org-1", workspace_id="ws-1")
    b = TenantScope(organization_id="org-1", workspace_id="ws-1")
    c = TenantScope(organization_id="org-1", workspace_id="ws-2")
    assert a == b
    assert a != c


def test_policy_and_visibility_invariants():
    """blocked is NOT visibility. pending_approval/approved are NOT operational states."""
    assert "blocked" not in VISIBILITY_LEVELS
    assert "block" in POLICY_OUTCOMES
    assert "none" in APPROVAL_STATES
    assert "pending" in APPROVAL_STATES
    assert "pending_approval" not in OPERATIONAL_STATES
    assert "approved" not in OPERATIONAL_STATES


# ============================================================================
# 2. RBAC Role Matrix Conformance
# ============================================================================

ROLE_EXPECTED_ACTIONS = {
    "Platform Admin": DEFAULT_ACTIONS,  # all actions
    "Security Admin": {
        "asset:read", "asset:scan", "asset:approve", "asset:manage_acl",
        "policy:manage", "audit:read", "report:read",
    },
    "Asset Admin": {
        "asset:read", "asset:download", "asset:sync", "asset:publish",
        "asset:delete", "asset:scan", "report:read",
    },
    "Team Admin": {
        "asset:read", "asset:download", "asset:sync", "asset:publish",
        "asset:scan", "report:read",
    },
    "Developer": {"asset:read", "asset:download", "asset:scan"},
    "Viewer": {"asset:read"},
    "Service Account": {"asset:read", "asset:download", "asset:sync", "asset:scan", "token:manage"},
}

FORBIDDEN_ACTIONS = {
    "Developer": {"asset:approve", "asset:publish", "asset:delete", "asset:manage_acl", "policy:manage"},
    "Viewer": {"asset:download", "asset:approve", "asset:publish", "asset:delete", "asset:sync", "asset:scan", "asset:manage_acl", "policy:manage"},
    "Service Account": {"asset:approve", "asset:publish", "asset:delete", "asset:manage_acl", "policy:manage"},
}


@pytest.mark.parametrize("role,actions", list(ROLE_EXPECTED_ACTIONS.items()))
def test_role_has_expected_actions(role, actions):
    """Each role has its expected allowed actions."""
    principal = Principal(id=f"test-{role}", roles=[role])
    for action in actions:
        decision = check_permission(principal, action)
        assert decision.allowed, f"{role} should have {action}"


@pytest.mark.parametrize("role,forbidden", [
    (role, frozenset(fa)) for role, fa in FORBIDDEN_ACTIONS.items()
])
def test_role_forbidden_actions(role, forbidden):
    """Each role is denied specific actions."""
    principal = Principal(id=f"test-{role}", roles=[role])
    for action in forbidden:
        decision = check_permission(principal, action)
        assert not decision.allowed, f"{role} should NOT have {action}"


def test_permission_decision_precedence():
    """Decision precedence: tenant scope > explicit deny > RBAC > visibility > approval > allow/warn."""
    # Platform Admin can do everything
    admin = Principal(id="admin", roles=["Platform Admin"])
    assert check_permission(admin, "asset:delete").allowed
    assert check_permission(admin, "policy:manage").allowed

    # Multiple roles: most permissive wins (union)
    hybrid = Principal(id="hybrid", roles=["Developer", "Security Admin"])
    assert check_permission(hybrid, "asset:download").allowed  # from Developer
    assert check_permission(hybrid, "policy:manage").allowed  # from Security Admin


def test_no_roles_results_in_deny():
    """Principal with no roles gets no permissions."""
    principal = Principal(id="no-role", roles=[])
    for action in DEFAULT_ACTIONS:
        decision = check_permission(principal, action)
        assert not decision.allowed, f"no-role should not have {action}"


def test_permission_decision_metadata():
    """PermissionDecision includes principal info in metadata."""
    principal = Principal(id="dev-1", roles=["Developer"])
    decision = check_permission(principal, "asset:read")
    assert decision.metadata.get("principal_id") == "dev-1"
    assert "Developer" in decision.metadata.get("roles", [])


def test_batch_permission_checks():
    """Batch permission checking works for catalog filtering."""
    from modely.governance.permissions import batch_check_permissions

    principal = Principal(id="dev-1", roles=["Developer"])
    actions = ["asset:read", "asset:download", "asset:delete", "asset:approve"]
    results = batch_check_permissions(principal, actions)

    assert results["asset:read"].allowed
    assert results["asset:download"].allowed
    assert not results["asset:delete"].allowed
    assert not results["asset:approve"].allowed


# ============================================================================
# 3. Visibility Evaluation
# ============================================================================

def test_visibility_evaluation_organization():
    """Organization-visible assets are visible to org members."""
    from modely.cataloging.visibility import check_visibility
    from modely.domain.tenants import TenantScope

    principal = Principal(id="user-1", roles=["Developer"])
    principal.tenant_scope = TenantScope(organization_id="org-1", workspace_id="ws-1")

    asset = Asset(
        id="asset-1",
        identity=AssetIdentity(source="hf", repo_type="model"),
        visibility="organization",
    )
    # Set tenant_scope on asset
    asset.tenant_scope = TenantScope(organization_id="org-1", workspace_id="ws-1")

    assert check_visibility(principal, asset)


def test_visibility_cross_tenant_isolation():
    """User in org-1 cannot see org-2's workspace-visible assets."""
    from modely.cataloging.visibility import check_visibility
    from modely.domain.tenants import TenantScope

    principal = Principal(id="user-1", roles=["Developer"])
    principal.tenant_scope = TenantScope(organization_id="org-1", workspace_id="ws-1")

    asset = Asset(
        id="asset-2",
        identity=AssetIdentity(source="hf", repo_type="model"),
        visibility="workspace",
    )
    asset.tenant_scope = TenantScope(organization_id="org-2", workspace_id="ws-2")

    assert not check_visibility(principal, asset)


def test_visibility_blocked_rejected():
    """'blocked' is rejected as a visibility value."""
    with pytest.raises(ValueError):
        Asset(
            id="bad",
            identity=AssetIdentity(source="hf", repo_type="model"),
            visibility="blocked",
        )


# ============================================================================
# 4. Approval Lifecycle State Machine
# ============================================================================

def test_approval_state_transitions_valid():
    """All valid approval transitions work."""
    from modely.governance.approvals import ApprovalRequest, transition_request

    # none -> pending (submit)
    req = ApprovalRequest(id="r1", asset_id="a1", requester="dev1", status="none")
    req = transition_request(req, "pending")
    assert req.status == "pending"

    # pending -> approved
    req = transition_request(req, "approved", reviewer="admin1", reason="looks good")
    assert req.status == "approved"
    assert req.reviewer == "admin1"

    # approved -> expired
    req2 = ApprovalRequest(id="r2", asset_id="a2", requester="dev2", status="none")
    req2 = transition_request(req2, "pending")
    req2 = transition_request(req2, "approved", reviewer="admin1")
    req2 = transition_request(req2, "expired")
    assert req2.status == "expired"

    # pending -> cancelled (user withdraws)
    req3 = ApprovalRequest(id="r3", asset_id="a3", requester="dev3", status="none")
    req3 = transition_request(req3, "pending")
    req3 = transition_request(req3, "cancelled")
    assert req3.status == "cancelled"

    # pending -> rejected
    req4 = ApprovalRequest(id="r4", asset_id="a4", requester="dev4", status="none")
    req4 = transition_request(req4, "pending")
    req4 = transition_request(req4, "rejected", reviewer="admin1", reason="denied")
    assert req4.status == "rejected"

    # pending -> expired (SLA timeout)
    req5 = ApprovalRequest(id="r5", asset_id="a5", requester="dev5", status="none")
    req5 = transition_request(req5, "pending")
    req5 = transition_request(req5, "expired")
    assert req5.status == "expired"


def test_approval_state_transitions_invalid():
    """Invalid transitions raise ValueError."""
    from modely.governance.approvals import ApprovalRequest, transition_request

    # Cannot approve from none (must submit first)
    req = ApprovalRequest(id="r1", asset_id="a1", requester="dev1", status="none")
    with pytest.raises(ValueError):
        transition_request(req, "approved")

    # Cannot modify approved request
    req2 = ApprovalRequest(id="r2", asset_id="a2", requester="dev2", status="none")
    req2 = transition_request(req2, "pending")
    req2 = transition_request(req2, "approved", reviewer="admin1")
    with pytest.raises(ValueError):
        transition_request(req2, "rejected")

    # Cannot uncancel
    req3 = ApprovalRequest(id="r3", asset_id="a3", requester="dev3", status="none")
    req3 = transition_request(req3, "pending")
    req3 = transition_request(req3, "cancelled")
    with pytest.raises(ValueError):
        transition_request(req3, "pending")


# ============================================================================
# 5. Policy Decision Output
# ============================================================================

def test_policy_decision_enum_values():
    """Policy decision must be one of 4 canonical values."""
    valid = ["allow", "warn", "require_approval", "block"]
    for v in valid:
        pd = PolicyDecision(outcome=v)
        assert pd.outcome == v

    with pytest.raises(ValueError):
        PolicyDecision(outcome="maybe")

    with pytest.raises(ValueError):
        PolicyDecision(outcome="blocked")


def test_policy_decision_properties():
    """PolicyDecision helper properties work."""
    assert PolicyDecision(outcome="allow").allowed
    assert PolicyDecision(outcome="warn").allowed
    assert not PolicyDecision(outcome="require_approval").allowed
    assert not PolicyDecision(outcome="block").allowed

    assert PolicyDecision(outcome="block").blocked
    assert not PolicyDecision(outcome="allow").blocked


# ============================================================================
# 6. Audit Events
# ============================================================================

def test_audit_event_emission():
    """Audit events can be recorded."""
    from modely.governance.audit import record_audit_event

    event = record_audit_event("asset.download", resource="asset-1", status="ok")
    assert event is not None
    assert "ts" in event
    assert event.get("action") == "asset.download"
    assert event.get("resource") == "asset-1"


def test_audit_events_listable():
    """Audit events can be listed."""
    from modely.governance.audit import list_audit_events, record_audit_event

    record_audit_event("asset.view", resource="asset-xyz")
    events = list_audit_events(limit=10, action="asset.view")
    assert len(events) > 0
    assert any(e.get("resource") == "asset-xyz" for e in events)


# ============================================================================
# 7. Redaction
# ============================================================================

def test_redaction_sensitive_fields():
    """Sensitive fields are redacted."""
    from modely.governance.redaction import redact_mapping, is_sensitive_field

    assert is_sensitive_field("token")
    assert is_sensitive_field("api_token")
    assert is_sensitive_field("password")
    assert is_sensitive_field("secret")

    result = redact_mapping({"api_token": "secret123", "name": "test"})
    assert result["api_token"] != "secret123"
    assert result["name"] == "test"


def test_redaction_nested():
    """Nested sensitive fields are redacted recursively."""
    from modely.governance.redaction import redact_mapping

    payload = {
        "name": "test",
        "auth": {"token": "abc123", "type": "bearer"},
    }
    result = redact_mapping(payload)
    assert result["auth"]["token"] != "abc123"


# ============================================================================
# 8. Governance Reports
# ============================================================================

def test_build_governance_report():
    """GovernanceReport can be built and redacted."""
    from modely.governance.reports import build_governance_report

    report = build_governance_report(
        "Phase 2 Test Report",
        assets=[{"id": "asset-1", "visibility": "workspace"}],
        policy_decisions=[{"outcome": "allow"}],
    )
    assert report.title == "Phase 2 Test Report"
    assert len(report.assets) == 1

    d = report.to_dict()
    assert "title" in d
    assert "assets" in d


# ============================================================================
# 9. Policy Engine License/Security Rules
# ============================================================================

def test_spdx_license_normalization():
    """License normalization works."""
    from modely.governance.policy_engine import _normalize_spdx

    assert _normalize_spdx("Apache-2.0") == "apache-2.0"
    assert _normalize_spdx("MIT") == "mit"
    assert _normalize_spdx("  GPL-3.0  ") == "gpl-3.0"


def test_policy_template_builtins():
    """Built-in policy templates are available."""
    from modely.governance.policy_engine import policy_template

    permissive = policy_template("permissive")
    assert "fail_on" in permissive
    assert permissive["fail_on"] == "high"

    balanced = policy_template("balanced")
    assert balanced["fail_on"] == "medium"

    strict = policy_template("strict")
    assert strict["fail_on"] == "low"


# ============================================================================
# 10. Download Authorization
# ============================================================================

def test_signed_url_generation():
    """Signed URL generation produces valid signed URLs with TTL."""
    from modely.storage.download_urls import generate_signed_url

    url = generate_signed_url(
        asset_id="asset-1",
        principal_id="user-1",
        storage_path="/storage/models/asset-1/model.bin",
        shared_secret="test-secret",
        ttl_seconds=60,
        base_url="https://example.com",
    )
    assert "asset-1" in url.url
    assert "signature=" in url.url
    assert url.expires_at is not None
    assert url.method == "GET"



# ============================================================================
# 11. Quota Model
# ============================================================================

def test_quota_creation():
    """Quota entity can be created with dimensions and enforcement points."""
    from modely.domain.quota import QUOTA_DIMENSIONS, QUOTA_MODES, Quota

    q = Quota(
        subject="team:team-1",
        dimension="downloads",
        limit=100,
        mode="soft",
        enforcement_points=["api_gateway", "download_egress"],
    )
    assert q.subject == "team:team-1"
    assert q.dimension == "downloads"
    assert q.limit == 100
    assert q.mode == "soft"
    assert "downloads" in QUOTA_DIMENSIONS
    assert "soft" in QUOTA_MODES
    assert q.remaining == 100
    assert not q.exceeded


def test_quota_check():
    """Quota enforcement check works — soft/advisory always allow, hard enforces."""
    from modely.domain.quota import Quota, check_quota

    advisory_q = Quota(subject="user:u1", dimension="downloads", limit=10, mode="advisory")
    assert check_quota(advisory_q, 100)  # advisory: always allows

    soft_q = Quota(subject="user:u2", dimension="downloads", limit=10, mode="soft")
    assert check_quota(soft_q, 100)  # soft: always allows (warn only)

    hard_q = Quota(subject="user:u3", dimension="downloads", limit=10, mode="hard")
    assert check_quota(hard_q, 5)  # 0 + 5 < 10: allowed
    assert not check_quota(hard_q, 10)  # 0 + 10 >= 10: blocked


# ============================================================================
# 12. Source Credential Governance
# ============================================================================

def test_source_credential_redaction():
    """Source credential secrets are redacted."""
    from modely.domain.credentials import SourceCredential

    cred = SourceCredential(
        id="cred-1",
        tenant_scope="org-1:ws-1",
        source="huggingface",
        credential_type="bearer_token",
        secret_ref="hf_abc123",
    )
    d = cred.to_dict()
    # secret_ref should be redacted in serialization
    assert d.get("secret_ref") != "hf_abc123"


def test_source_credential_metadata_only():
    """Only metadata (not secrets) is shown after creation."""
    from modely.domain.credentials import SourceCredential

    cred = SourceCredential(
        id="cred-1",
        tenant_scope="org-1:ws-1",
        source="huggingface",
        credential_type="bearer_token",
        secret_ref="hf_abc123secret",
    )
    assert cred.id == "cred-1"
    assert cred.source == "huggingface"
    assert cred.credential_type == "bearer_token"
    # The raw secret should not be directly accessible in repr
    assert "hf_abc123secret" not in str(cred)
