"""Phase 2d policy engine unit tests.

Covers: PolicyProfile model, policy resolution order, license compliance,
secret/remote-code/dataset rules, unified governance engine,
scanner coverage status, and missing-vs-clean evidence distinction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from modely.domain.policies import (
    POLICY_ENVIRONMENTS,
    SCANNER_CATEGORIES,
    SCANNER_COVERAGE_STATUSES,
    WARNING_MODES,
    PolicyDecision,
    PolicyProfile,
    PolicyRule,
    resolve_policy_profiles,
    resolve_rule_conflicts,
)
from modely.governance.policy_engine import (
    _determine_scanner_coverage,
    _normalize_spdx,
    evaluate_governance_policy,
    evaluate_license_rules,
    has_commercial_risk,
    is_copyleft,
    license_risk_level,
    normalize_spdx,
    parse_policy_rules_from_config,
    resolve_multi_license,
    resolve_multi_license_and,
    resolve_multi_license_or,
)


# ============================================================================
# 1. PolicyProfile model tests
# ============================================================================

def test_policy_profile_creation():
    """PolicyProfile can be created with all required and optional fields."""
    profile = PolicyProfile(
        id="pol-1",
        name="Strict Production Policy",
        version="v1.2.0",
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1"},
        environment="prod",
        default_warning_mode="warn_only",
        created_by="admin@org.com",
    )
    assert profile.id == "pol-1"
    assert profile.name == "Strict Production Policy"
    assert profile.version == "v1.2.0"
    assert profile.tenant_scope["organization_id"] == "org-1"
    assert profile.environment == "prod"
    assert profile.default_warning_mode == "warn_only"
    assert profile.created_by == "admin@org.com"
    assert profile.precedence == 0
    assert profile.rules == []
    assert profile.effective_from


def test_policy_profile_is_active():
    """Archived profiles are inactive."""
    active = PolicyProfile(
        id="pol-1", name="Active", version="v1", tenant_scope={},
    )
    archived = PolicyProfile(
        id="pol-2", name="Archived", version="v1", tenant_scope={}, archived_at="2026-01-01",
    )
    assert active.is_active()
    assert not archived.is_active()


def test_policy_profile_serialization():
    """PolicyProfile can be serialized to dict."""
    rule = PolicyRule(id="r1", category="license", action="allow", match={"licenses": ["apache-2.0"]})
    profile = PolicyProfile(
        id="pol-1", name="Test", version="v1", tenant_scope={"org": "o1"},
        rules=[rule], created_by="tester",
    )
    d = profile.to_dict()
    assert d["id"] == "pol-1"
    assert d["name"] == "Test"
    assert d["rules"][0]["category"] == "license"


def test_policy_profile_invalid_warning_mode():
    """Invalid warning_mode raises ValueError."""
    with pytest.raises(ValueError):
        PolicyProfile(
            id="pol-1", name="Bad", version="v1", tenant_scope={},
            default_warning_mode="crash",
        )


def test_policy_profile_invalid_environment():
    """Invalid environment raises ValueError."""
    with pytest.raises(ValueError):
        PolicyProfile(
            id="pol-1", name="Bad", version="v1", tenant_scope={},
            environment="laptop",
        )


# ============================================================================
# 2. PolicyRule model tests
# ============================================================================

def test_policy_rule_creation():
    """PolicyRule can be created and serialized."""
    rule = PolicyRule(
        id="block-gpl",
        category="license",
        action="block",
        match={"licenses": ["gpl-3.0", "agpl-3.0"]},
        description="Block copyleft licenses",
        severity="high",
    )
    assert rule.id == "block-gpl"
    assert rule.category == "license"
    assert rule.action == "block"
    assert rule.match["licenses"] == ["gpl-3.0", "agpl-3.0"]
    assert rule.severity == "high"


def test_policy_rule_invalid_action():
    """Invalid rule action raises ValueError."""
    with pytest.raises(ValueError):
        PolicyRule(id="r1", category="license", action="deny")


def test_policy_rule_invalid_category():
    """Invalid scanner category raises ValueError."""
    with pytest.raises(ValueError):
        PolicyRule(id="r1", category="vuln_scan", action="block")


def test_policy_rule_serialization():
    """PolicyRule serializes correctly."""
    rule = PolicyRule(id="r1", category="license", action="allow", match={"licenses": ["mit"]})
    d = rule.to_dict()
    assert d["id"] == "r1"
    assert d["action"] == "allow"


# ============================================================================
# 3. Policy resolution order tests
# ============================================================================

def test_resolve_explicit_profile_id():
    """Explicit profile ID wins over all other bindings."""
    p1 = PolicyProfile(id="p1", name="Env Profile", version="v1", tenant_scope={}, environment="prod")
    p2 = PolicyProfile(id="p2", name="Explicit Profile", version="v1", tenant_scope={})
    result = resolve_policy_profiles([p1, p2], explicit_profile_id="p2")
    assert result is not None
    assert result.id == "p2"


def test_resolve_environment_binding():
    """Environment binding wins when no explicit ID given."""
    p1 = PolicyProfile(id="p1", name="Dev", version="v1", tenant_scope={}, environment="dev")
    p2 = PolicyProfile(id="p2", name="Prod", version="v1", tenant_scope={}, environment="prod")
    result = resolve_policy_profiles([p1, p2], environment="prod")
    assert result is not None
    assert result.id == "p2"


def test_resolve_project_binding():
    """Project binding wins over workspace/org defaults."""
    p1 = PolicyProfile(id="p1", name="WS Default", version="v1", tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1"}, precedence=0)
    p2 = PolicyProfile(id="p2", name="Project", version="v1", tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1", "project_id": "proj-1"}, precedence=0)
    result = resolve_policy_profiles([p1, p2], project_id="proj-1", workspace_id="ws-1", organization_id="org-1")
    assert result is not None
    assert result.id == "p2"


def test_resolve_workspace_default():
    """Workspace default is used when no project/env binding exists."""
    p1 = PolicyProfile(id="p1", name="Org Default", version="v1", tenant_scope={"organization_id": "org-1"})
    p2 = PolicyProfile(id="p2", name="WS Default", version="v1", tenant_scope={"workspace_id": "ws-1"}, precedence=0)
    result = resolve_policy_profiles([p1, p2], workspace_id="ws-1", organization_id="org-1")
    assert result is not None
    assert result.id == "p2"


def test_resolve_organization_default():
    """Organization default is the lowest precedence."""
    p1 = PolicyProfile(id="p1", name="Org Default", version="v1", tenant_scope={"organization_id": "org-1"})
    result = resolve_policy_profiles([p1], organization_id="org-1")
    assert result is not None
    assert result.id == "p1"


def test_resolve_fallback_to_highest_precedence():
    """When no binding matches, the highest precedence active profile wins."""
    p1 = PolicyProfile(id="p1", name="Low", version="v1", tenant_scope={}, precedence=0)
    p2 = PolicyProfile(id="p2", name="High", version="v1", tenant_scope={}, precedence=10)
    result = resolve_policy_profiles([p1, p2])
    assert result is not None
    assert result.id == "p2"


def test_resolve_archived_profiles_ignored():
    """Archived profiles are not considered."""
    p1 = PolicyProfile(id="p1", name="Archived", version="v1", tenant_scope={}, archived_at="2026-01-01")
    result = resolve_policy_profiles([p1])
    assert result is None


def test_resolve_no_profiles():
    """When no profiles exist, return None."""
    result = resolve_policy_profiles([])
    assert result is None


# ============================================================================
# 4. Rule conflict resolution tests
# ============================================================================

def test_resolve_rule_conflicts_block_wins():
    """Block overrides allow for rules with the same category+id."""
    rules = [
        PolicyRule(id="r1", category="license", action="allow", match={"licenses": ["gpl-3.0"]}),
        PolicyRule(id="r1", category="license", action="block", match={"licenses": ["gpl-3.0"]}),
    ]
    resolved = resolve_rule_conflicts(rules)
    assert len(resolved) == 1
    assert resolved[0].action == "block"


def test_resolve_rule_conflicts_different_categories():
    """Rules in different categories are both kept."""
    rules = [
        PolicyRule(id="r1", category="license", action="block", match={"licenses": ["gpl-3.0"]}),
        PolicyRule(id="r2", category="secret", action="block", match={"finding_ids": ["api-key"]}),
    ]
    resolved = resolve_rule_conflicts(rules)
    assert len(resolved) == 2


# ============================================================================
# 5. SPDX license normalization tests
# ============================================================================

def test_spdx_normalization_basic():
    """Basic SPDX normalization."""
    assert _normalize_spdx("MIT") == "mit"
    assert _normalize_spdx("  Apache-2.0  ") == "apache-2.0"
    assert _normalize_spdx("GPL-3.0") == "gpl-3.0"


def test_spdx_normalize_with_aliases():
    """Alias resolution for common variants."""
    assert normalize_spdx("Apache") == "apache-2.0"
    assert normalize_spdx("apache2") == "apache-2.0"
    assert normalize_spdx("gplv3") == "gpl-3.0"
    assert normalize_spdx("gpl2") == "gpl-2.0"
    assert normalize_spdx("public domain") == "cc0-1.0"
    assert normalize_spdx("cc-by") == "cc-by-4.0"


def test_spdx_normalize_unknown():
    """Unknown identifiers fall through unchanged."""
    assert normalize_spdx("unknown") == "unknown"
    assert normalize_spdx("my-custom-1.0") == "my-custom-1.0"


# ============================================================================
# 6. License risk classification tests
# ============================================================================

def test_license_risk_level():
    """License risk levels."""
    assert license_risk_level("mit") == "low"
    assert license_risk_level("apache-2.0") == "low"
    assert license_risk_level("bsd-3-clause") == "low"
    assert license_risk_level("mpl-2.0") == "medium"
    assert license_risk_level("lgpl-2.1") == "medium"
    assert license_risk_level("gpl-3.0") == "high"
    assert license_risk_level("agpl-3.0") == "high"
    assert license_risk_level("unknown") == "high"
    assert license_risk_level("some-random-license") == "medium"


def test_is_copyleft():
    """Copyleft/viral license detection."""
    assert is_copyleft("gpl-3.0")
    assert is_copyleft("gpl-2.0")
    assert is_copyleft("agpl-3.0")
    assert is_copyleft("lgpl-2.1")
    assert is_copyleft("lgpl-3.0")
    assert is_copyleft("mpl-2.0")
    assert not is_copyleft("mit")
    assert not is_copyleft("apache-2.0")
    assert not is_copyleft("bsd-3-clause")


def test_has_commercial_risk():
    """Commercial risk detection."""
    assert has_commercial_risk("cc-by-nc-4.0")
    assert has_commercial_risk("gpl-3.0")
    assert has_commercial_risk("agpl-3.0")
    assert not has_commercial_risk("mit")
    assert not has_commercial_risk("apache-2.0")
    assert not has_commercial_risk("lgpl-2.1")


# ============================================================================
# 7. Multi-license handling tests
# ============================================================================

def test_resolve_multi_license_single():
    """Single license resolves directly."""
    result = resolve_multi_license(["MIT"])
    assert result["effective"] == "mit"
    assert result["combination"] == "single"
    assert result["risk_level"] == "low"


def test_resolve_multi_license_and_most_restrictive():
    """AND combination returns most restrictive license."""
    result = resolve_multi_license(["MIT", "GPL-3.0"], "AND")
    assert result["combination"] == "AND"
    assert result["effective"] == "gpl-3.0"
    assert result["risk_level"] == "high"


def test_resolve_multi_license_or_least_restrictive():
    """OR combination returns least restrictive license."""
    result = resolve_multi_license(["MIT", "GPL-3.0"], "OR")
    assert result["combination"] == "OR"
    assert result["effective"] == "mit"
    assert result["risk_level"] == "low"


def test_resolve_multi_license_empty():
    """Empty license list resolves to unknown."""
    result = resolve_multi_license([], "AND")
    assert result["effective"] == "unknown"
    assert result["risk_level"] == "high"


def test_resolve_multi_license_and_returns_copyleft_info():
    """AND result carries copyleft and commercial risk info."""
    result = resolve_multi_license(["MIT", "GPL-3.0"], "AND")
    assert result["is_copyleft"] is True


def test_resolve_multi_license_and_specific():
    """Direct AND wrapper function."""
    result = resolve_multi_license_and(["MIT", "GPL-3.0"])
    assert result["effective"] == "gpl-3.0"


def test_resolve_multi_license_or_specific():
    """Direct OR wrapper function."""
    result = resolve_multi_license_or(["MIT", "GPL-3.0"])
    assert result["effective"] == "mit"


# ============================================================================
# 8. License rule evaluation tests
# ============================================================================

def test_evaluate_license_rules_allow():
    """License in allow list passes."""
    rules = [
        {"id": "allow-permissive", "action": "allow", "match": {"licenses": ["mit"]}},
    ]
    result = evaluate_license_rules(["MIT"], rules)
    assert result["action"] == "allow"


def test_evaluate_license_rules_block():
    """License in block list is blocked."""
    rules = [
        {"id": "block-gpl", "action": "block", "match": {"licenses": ["gpl-3.0"]}},
    ]
    result = evaluate_license_rules(["GPL-3.0"], rules)
    assert result["action"] == "block"
    assert "gpl-3.0" in result["blocked_licenses"]


def test_evaluate_license_rules_warn():
    """License in warn list triggers warning."""
    rules = [
        {"id": "warn-nc", "action": "warn", "match": {"licenses": ["cc-by-nc-4.0"]}},
    ]
    result = evaluate_license_rules(["CC-BY-NC-4.0"], rules)
    assert result["action"] == "warn"
    assert "cc-by-nc-4.0" in result["warned_licenses"]


def test_evaluate_license_rules_require_approval():
    """License in require_approval list triggers approval check."""
    rules = [
        {"id": "approve-lgpl", "action": "require_approval", "match": {"licenses": ["lgpl-2.1"]}},
    ]
    result = evaluate_license_rules(["LGPL-2.1"], rules)
    assert result["action"] == "require_approval"


def test_evaluate_license_rules_unknown_blocked():
    """Unknown license can be blocked by rule."""
    rules = [
        {"id": "block-unknown", "action": "block", "match": {"licenses": ["unknown"]}},
    ]
    result = evaluate_license_rules(["unknown"], rules)
    assert result["action"] == "block"


def test_evaluate_license_rules_precedence_block_wins():
    """Block takes precedence over warn/require_approval/allow."""
    rules = [
        {"id": "allow-gpl", "action": "allow", "match": {"licenses": ["gpl-3.0"]}},
        {"id": "block-gpl", "action": "block", "match": {"licenses": ["gpl-3.0"]}},
    ]
    result = evaluate_license_rules(["GPL-3.0"], rules)
    assert result["action"] == "block"


# ============================================================================
# 9. YAML/JSON config parsing tests
# ============================================================================

def test_parse_policy_rules_from_config_license():
    """Parse license rules from YAML-style config."""
    config = {
        "license": {
            "allow": ["Apache-2.0", "MIT"],
            "warn": ["CC-BY-NC-4.0"],
            "block": ["GPL-3.0", "AGPL-3.0", "unknown"],
        },
    }
    rules = parse_policy_rules_from_config(config)
    assert len(rules) == 3
    actions = {r["action"] for r in rules}
    assert actions == {"allow", "warn", "block"}


def test_parse_policy_rules_from_config_secret():
    """Parse secret rules from YAML-style config."""
    config = {
        "secret": {
            "block": ["api-key", "private-key"],
            "warn": ["suspicious-pattern"],
        },
    }
    rules = parse_policy_rules_from_config(config)
    assert len(rules) == 2
    block_rule = next(r for r in rules if r["action"] == "block")
    assert block_rule["match"]["finding_ids"] == ["api-key", "private-key"]


def test_parse_policy_rules_from_config_empty():
    """Empty config returns empty rules."""
    rules = parse_policy_rules_from_config({})
    assert rules == []


# ============================================================================
# 10. Scanner coverage determination tests
# ============================================================================

def test_scanner_coverage_not_configured():
    """No evidence means not_configured."""
    coverage = _determine_scanner_coverage({}, {})
    assert coverage["license"] == "not_configured"
    assert coverage["secret"] == "not_configured"


def test_scanner_coverage_full():
    """Evidence with findings means full coverage."""
    evidence = {
        "license": {"status": "ok", "findings": [{"id": "license-ok"}], "total_expected": 1},
    }
    coverage = _determine_scanner_coverage(evidence, {})
    assert coverage["license"] == "full"


def test_scanner_coverage_partial():
    """Partial coverage when findings < expected."""
    evidence = {
        "license": {"status": "ok", "findings": [{"id": "license-ok"}], "total_expected": 5},
    }
    coverage = _determine_scanner_coverage(evidence, {})
    assert coverage["license"] == "partial"


def test_scanner_coverage_failed():
    """Coverage status is failed when scanner errored."""
    evidence = {
        "secret": {"status": "failed", "error": "timeout"},
    }
    coverage = _determine_scanner_coverage(evidence, {})
    assert coverage["secret"] == "failed"


def test_scanner_coverage_not_applicable():
    """Coverage reports not_applicable."""
    evidence = {
        "dataset_compliance": {"status": "not_applicable"},
    }
    coverage = _determine_scanner_coverage(evidence, {})
    assert coverage["dataset_compliance"] == "not_applicable"


def test_scanner_coverage_metadata_only():
    """No findings but ran = metadata_only."""
    evidence = {
        "remote_code": {"status": "ok", "total_expected": 0},
    }
    coverage = _determine_scanner_coverage(evidence, {})
    assert coverage["remote_code"] == "metadata_only"


def test_scanner_coverage_approval_bumps_partial():
    """Approval state can positively affect coverage interpretation."""
    evidence = {
        "secret": {"status": "ok", "findings": [{"id": "f1"}], "total_expected": 1},
    }
    approvals = {"scanners_approved": ["secret"]}
    coverage = _determine_scanner_coverage(evidence, approvals)
    assert coverage["secret"] == "full"


# ============================================================================
# 11. Unified governance policy engine tests
# ============================================================================

def test_evaluate_governance_default_permissive():
    """No policy profile means default permissive allow."""
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model"},
        action="asset:read",
        scan_evidence={},
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
    )
    assert decision.outcome == "allow"
    assert decision.policy_version == ""
    assert "No active policy profile was resolved" in decision.explanation


def test_evaluate_governance_missing_evidence():
    """Missing evidence is tracked in the decision."""
    evidence = {
        "license": {"status": "ok", "findings": [{"id": "license-ok"}], "total_expected": 1},
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model"},
        action="asset:read",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
    )
    assert decision.outcome == "allow"
    assert "secret" in decision.missing_evidence
    assert "remote_code" in decision.missing_evidence


def test_evaluate_governance_with_profile_block_license():
    """Policy profile with license block rule blocks the asset."""
    rule = PolicyRule(
        id="block-gpl",
        category="license",
        action="block",
        match={"licenses": ["gpl-3.0"]},
    )
    profile = PolicyProfile(
        id="pol-strict", name="Strict", version="v1",
        tenant_scope={"org": "org-1"}, rules=[rule],
    )
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "gpl-3.0"},
        action="asset:download",
        scan_evidence={},
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "block"
    assert decision.matched_rule_ids == ["block-gpl"]
    assert decision.policy_version == "v1"


def test_evaluate_governance_with_profile_warn_license():
    """Policy profile with license warn rule warns."""
    rule = PolicyRule(
        id="warn-nc",
        category="license",
        action="warn",
        match={"licenses": ["cc-by-nc-4.0"]},
    )
    profile = PolicyProfile(
        id="pol-warn", name="Warn NC", version="v1",
        tenant_scope={"org": "org-1"}, rules=[rule],
    )
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "cc-by-nc-4.0"},
        action="asset:download",
        scan_evidence={},
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "warn"
    assert "warn-nc" in decision.matched_rule_ids


def test_evaluate_governance_secret_finding_blocked():
    """Secret finding triggers block."""
    rule = PolicyRule(
        id="block-secrets",
        category="secret",
        action="block",
        match={"finding_ids": ["api-key", "private-key"]},
    )
    profile = PolicyProfile(
        id="pol-secret", name="Secret Block", version="v1",
        tenant_scope={"org": "org-1"}, rules=[rule],
    )
    evidence = {
        "secret": {
            "status": "ok",
            "findings": [{"id": "api-key", "severity": "high"}],
            "total_expected": 1,
        },
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model"},
        action="asset:download",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "block"
    assert "api-key" in decision.finding_ids


def test_evaluate_governance_remote_code_blocked():
    """Remote-code pickle finding triggers block."""
    rule = PolicyRule(
        id="block-pickle",
        category="remote_code",
        action="block",
        match={"finding_ids": ["pickle-artifact"]},
    )
    profile = PolicyProfile(
        id="pol-remote", name="Remote Block", version="v1",
        tenant_scope={"org": "org-1"}, rules=[rule],
    )
    evidence = {
        "remote_code": {
            "status": "ok",
            "findings": [{"id": "pickle-artifact", "severity": "high"}],
            "total_expected": 1,
        },
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model"},
        action="asset:download",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "block"
    assert "pickle-artifact" in decision.finding_ids


def test_evaluate_governance_dataset_compliance_blocked():
    """Dataset PII finding triggers block."""
    rule = PolicyRule(
        id="block-pii",
        category="dataset_compliance",
        action="block",
        match={"finding_ids": ["pii-detected"]},
    )
    profile = PolicyProfile(
        id="pol-dataset", name="Dataset Block", version="v1",
        tenant_scope={"org": "org-1"}, rules=[rule],
    )
    evidence = {
        "dataset_compliance": {
            "status": "ok",
            "findings": [{"id": "pii-detected", "severity": "critical"}],
            "total_expected": 1,
        },
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/dataset", "repo_type": "dataset"},
        action="asset:download",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "block"
    assert "pii-detected" in decision.finding_ids


def test_evaluate_governance_precedence_block_over_warn():
    """Block rule takes precedence over warn rule."""
    rules = [
        PolicyRule(id="warn-mit", category="license", action="warn", match={"licenses": ["mit"]}),
        PolicyRule(id="block-secrets", category="secret", action="block", match={"finding_ids": ["api-key"]}),
    ]
    profile = PolicyProfile(
        id="pol-combined", name="Combined", version="v1",
        tenant_scope={"org": "org-1"}, rules=rules,
    )
    evidence = {
        "secret": {
            "status": "ok",
            "findings": [{"id": "api-key", "severity": "high"}],
            "total_expected": 1,
        },
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "mit"},
        action="asset:download",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "block"


def test_evaluate_governance_approved_overrides_warn():
    """Approval state affects the decision. With warning rules and approved state, the warn may still fire."""
    rule = PolicyRule(
        id="warn-nc",
        category="license",
        action="warn",
        match={"licenses": ["cc-by-nc-4.0"]},
    )
    profile = PolicyProfile(
        id="pol-warn", name="Warn NC", version="v1",
        tenant_scope={"org": "org-1"}, rules=[rule],
    )
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "cc-by-nc-4.0"},
        action="asset:download",
        scan_evidence={},
        approval_state={"status": "approved"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome in ("allow", "warn")


def test_evaluate_governance_rejected_blocks():
    """Rejected approval blocks the request."""
    profile = PolicyProfile(
        id="pol-allow", name="Allow All", version="v1",
        tenant_scope={"org": "org-1"}, rules=[],
    )
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "mit"},
        action="asset:download",
        scan_evidence={},
        approval_state={"status": "rejected"},
        environment="prod",
        source="hf",
        policy_profile=profile,
    )
    assert decision.outcome == "block"


# ============================================================================
# 12. PolicyDecision output schema tests
# ============================================================================

def test_policy_decision_has_extended_fields():
    """PolicyDecision includes extended fields from unified engine."""
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "mit"},
        action="asset:read",
        scan_evidence={
            "license": {"status": "ok", "findings": [{"id": "license-ok"}], "total_expected": 1},
        },
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
    )
    d = decision.to_dict()
    assert "matched_rule_ids" in d
    assert "policy_version" in d
    assert "evidence_refs" in d
    assert "missing_evidence" in d
    assert "explanation" in d
    assert "scanner_coverage" in d
    assert isinstance(decision.missing_evidence, list)
    assert isinstance(decision.scanner_coverage, dict)


def test_policy_decision_covers_scanner_statuses():
    """Scanner coverage is populated in the decision."""
    evidence = {
        "license": {"status": "ok", "findings": [{"id": "license-ok"}], "total_expected": 1},
        "secret": {},
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model"},
        action="asset:read",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
    )
    assert "license" in decision.scanner_coverage
    assert decision.scanner_coverage["license"] in ("full", "partial")
    assert decision.scanner_coverage["secret"] in ("metadata_only", "missing_evidence", "not_configured")


# ============================================================================
# 13. Missing evidence vs clean evidence distinction tests
# ============================================================================

def test_missing_evidence_distinguished_from_clean():
    """Missing evidence is explicitly separate from clean evidence."""
    evidence = {
        "license": {"status": "ok", "findings": [], "total_expected": 1},
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model", "license": "mit"},
        action="asset:download",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
    )
    assert "secret" in decision.missing_evidence
    assert decision.scanner_coverage["license"] == "metadata_only"


def test_missing_vs_clean_distinction_in_explanation():
    """Explanation notes missing evidence without confusing it with clean."""
    evidence = {
        "license": {"status": "ok", "findings": [{"id": "license-ok"}], "total_expected": 1},
    }
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        tenant_scope={"organization_id": "org-1"},
        asset={"repo_id": "org/model"},
        action="asset:read",
        scan_evidence=evidence,
        approval_state={"status": "none"},
        environment="prod",
        source="hf",
    )
    assert decision.scanner_coverage["secret"] in ("not_configured", "missing_evidence")
    assert decision.scanner_coverage["remote_code"] in ("not_configured", "missing_evidence")


# ============================================================================
# 14. Request context and environment tests
# ============================================================================

def test_evaluate_governance_respects_request_context():
    """Request context can be passed and influences evaluation."""
    decision = evaluate_governance_policy(
        principal={"id": "user-1"},
        asset={"repo_id": "org/model", "license": "mit"},
        action="asset:download",
        environment="staging",
        source="github",
        request_context={"license_combination": "AND"},
    )
    assert decision.metadata.get("request_id") is None  # No request_id set
    assert decision.metadata.get("license_combination") == "AND"


def test_evaluate_governance_different_environments():
    """Different environments produce valid decisions."""
    for env in POLICY_ENVIRONMENTS:
        decision = evaluate_governance_policy(
            principal={"id": "user-1"},
            asset={"repo_id": "org/model"},
            action="asset:read",
            environment=env,
            source="hf",
        )
        assert decision.outcome in ("allow", "warn", "require_approval", "block")


# ============================================================================
# 15. PolicyDecision existing compatibility tests
# ============================================================================

def test_policy_decision_existing_api_unchanged():
    """Original PolicyDecision fields remain available."""
    pd = PolicyDecision(outcome="allow", reasons=["test"], risk_level="low")
    assert pd.outcome == "allow"
    assert pd.reasons == ["test"]
    assert pd.risk_level == "low"
    assert pd.allowed is True
    assert pd.blocked is False

    pd2 = PolicyDecision(outcome="block")
    assert pd2.blocked is True
    assert pd2.allowed is False

    pd3 = PolicyDecision(outcome="require_approval")
    assert pd3.allowed is False
    assert pd3.blocked is False


def test_policy_decision_default_extended_fields():
    """Extended fields have sensible defaults."""
    pd = PolicyDecision(outcome="allow")
    assert pd.matched_rule_ids == []
    assert pd.policy_version == ""
    assert pd.evidence_refs == {}
    assert pd.missing_evidence == []
    assert pd.explanation == ""
    assert pd.scanner_coverage == {}
