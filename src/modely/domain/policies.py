"""Policy decision domain objects and enterprise governance enums."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

PolicyOutcome = Literal["allow", "warn", "require_approval", "block"]
Visibility = Literal["organization", "workspace", "team", "project", "private", "restricted"]
ApprovalState = Literal["none", "pending", "approved", "rejected", "expired", "cancelled"]
OperationalState = Literal["discovered", "syncing", "synced", "scanning", "published", "archived", "failed"]
WarningMode = Literal["pass", "warn_only", "fail_ci"]
ScannerCoverage = Literal["full", "partial", "metadata_only", "missing_evidence", "not_configured", "not_applicable", "failed"]
PolicyEnvironment = Literal["dev", "staging", "prod", "training", "inference"]

POLICY_OUTCOMES: tuple[str, ...] = ("allow", "warn", "require_approval", "block")
VISIBILITY_LEVELS: tuple[str, ...] = ("organization", "workspace", "team", "project", "private", "restricted")
APPROVAL_STATES: tuple[str, ...] = ("none", "pending", "approved", "rejected", "expired", "cancelled")
OPERATIONAL_STATES: tuple[str, ...] = ("discovered", "syncing", "synced", "scanning", "published", "archived", "failed")
RESOURCE_ACTIONS: tuple[str, ...] = (
    "asset:read",
    "asset:download",
    "asset:sync",
    "asset:publish",
    "asset:approve",
    "asset:delete",
    "asset:scan",
    "asset:manage_acl",
    "report:read",
    "policy:manage",
    "audit:read",
    "token:manage",
)


WARNING_MODES: tuple[str, ...] = ("pass", "warn_only", "fail_ci")
SCANNER_COVERAGE_STATUSES: tuple[str, ...] = ("full", "partial", "metadata_only", "missing_evidence", "not_configured", "not_applicable", "failed")
POLICY_ENVIRONMENTS: tuple[str, ...] = ("dev", "staging", "prod", "training", "inference")
SCANNER_CATEGORIES: tuple[str, ...] = (
    "license",
    "secret",
    "remote_code",
    "dataset_compliance",
    "dependency_vulnerability",
    "sbom",
    "malware",
    "unsafe_artifact",
    "notebook",
    "shell_script",
    "executable_binary",
)


@dataclass
class PolicyRule:
    """A single policy rule with its match conditions and actions.

    Used within PolicyProfile.rules to define individual governance checks.
    """

    id: str
    category: str  # license, secret, remote_code, dataset_compliance, etc.
    action: str  # allow, warn, require_approval, block
    match: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in POLICY_OUTCOMES:
            raise ValueError(f"Unsupported policy rule action: {self.action}")
        if self.category not in SCANNER_CATEGORIES:
            raise ValueError(f"Unsupported scanner category: {self.category}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyProfile:
    """A versioned collection of policy rules scoped to a tenant and environment.

    Policy resolution order (highest to lowest precedence):
    1. explicit CLI/API parameter
    2. environment binding
    3. project binding
    4. workspace default
    5. organization default

    Rule conflict precedence within a profile:
    explicit block > explicit require_approval > warn > allow
    """

    id: str
    name: str
    version: str
    tenant_scope: str = ""  # e.g. "org:workspace:project"
    environment: str = "prod"
    rules: list[PolicyRule] = field(default_factory=list)
    precedence: int = 0
    default_warning_mode: str = "pass"
    created_by: str = ""
    effective_from: str = ""
    archived_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.default_warning_mode not in WARNING_MODES:
            raise ValueError(f"Unsupported warning mode: {self.default_warning_mode}")
        if self.environment not in POLICY_ENVIRONMENTS:
            raise ValueError(f"Unsupported policy environment: {self.environment}")
        if not self.effective_from:
            self.effective_from = datetime.now(timezone.utc).isoformat()

    def is_active(self) -> bool:
        """Return True if this profile is active (not archived)."""
        return self.archived_at is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyDecision:
    """Policy outcome shared by catalog, download, approval, and report flows.

    Extended from the original to support the unified governance policy engine.
    """

    outcome: str
    reasons: list[str] = field(default_factory=list)
    risk_level: str = "unknown"
    finding_ids: list[str] = field(default_factory=list)
    remediation_hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Extended fields for unified governance engine
    matched_rule_ids: list[str] = field(default_factory=list)
    policy_version: str = ""
    evidence_refs: dict[str, str] = field(default_factory=dict)
    missing_evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    scanner_coverage: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.outcome not in POLICY_OUTCOMES:
            raise ValueError(f"Unsupported policy outcome: {self.outcome}")

    @property
    def allowed(self) -> bool:
        return self.outcome in {"allow", "warn"}

    @property
    def blocked(self) -> bool:
        return self.outcome == "block"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_policy_profiles(
    profiles: list[PolicyProfile],
    *,
    explicit_profile_id: str = "",
    environment: str = "",
    project_id: str = "",
    workspace_id: str = "",
    organization_id: str = "",
) -> PolicyProfile | None:
    """Resolve the active policy profile by precedence order.

    Resolution order (highest to lowest):
    1. explicit CLI/API profile id
    2. environment binding
    3. project binding
    4. workspace default
    5. organization default

    Within the same precedence level, the highest-precedence active profile wins.

    Works with both string tenant_scope (e.g. "org1:ws1:proj1") and
    dict tenant_scope (e.g. {"organization_id": "org1", "workspace_id": "ws1"}).
    """
    active = [p for p in profiles if p.is_active()]

    def _matches_scope(profile: PolicyProfile, key: str, value: str) -> bool:
        """Check if a profile's tenant_scope contains the given key=value binding."""
        ts = profile.tenant_scope
        if isinstance(ts, dict):
            return ts.get(key) == value
        if isinstance(ts, str):
            if key == "organization_id" and value in ts:
                return True
            if key == "workspace_id" and value in ts:
                return True
            if key == "project_id" and f":{value}" in ts:
                return True
        return False

    # 1. Explicit profile ID
    if explicit_profile_id:
        for p in active:
            if p.id == explicit_profile_id:
                return p

    # 2. Environment binding
    for p in active:
        if environment and p.environment == environment and p.precedence >= 50:
            return p
    for p in active:
        if environment and p.environment == environment:
            return p

    # 3. Project binding
    if project_id:
        for p in active:
            if _matches_scope(p, "project_id", project_id):
                return p

    # 4. Workspace default
    if workspace_id:
        for p in active:
            if _matches_scope(p, "workspace_id", workspace_id) and p.precedence <= 0:
                return p

    # 5. Organization default
    if organization_id:
        for p in active:
            if _matches_scope(p, "organization_id", organization_id):
                return p

    # Fallback: highest precedence active profile
    if active:
        return sorted(active, key=lambda p: -p.precedence)[0]
    return None


def resolve_rule_conflicts(rules: list[PolicyRule]) -> list[PolicyRule]:
    """Resolve conflicts between rules with precedence: block > require_approval > warn > allow.

    When multiple rules match the same category, the most restrictive wins.
    """
    outcome_rank = {"block": 4, "require_approval": 3, "warn": 2, "allow": 1}
    resolved: dict[tuple[str, str], PolicyRule] = {}
    for rule in rules:
        key = (rule.category, rule.id)
        if key not in resolved or outcome_rank[rule.action] > outcome_rank[resolved[key].action]:
            resolved[key] = rule
    return list(resolved.values())


def is_visibility(value: str) -> bool:
    """Return whether value is a visibility level, not a policy/access state."""

    return value in VISIBILITY_LEVELS


def is_operational_state(value: str) -> bool:
    """Return whether value is an operational lifecycle state."""

    return value in OPERATIONAL_STATES


__all__ = [
    "APPROVAL_STATES",
    "OPERATIONAL_STATES",
    "POLICY_ENVIRONMENTS",
    "POLICY_OUTCOMES",
    "RESOURCE_ACTIONS",
    "SCANNER_CATEGORIES",
    "SCANNER_COVERAGE_STATUSES",
    "VISIBILITY_LEVELS",
    "WARNING_MODES",
    "ApprovalState",
    "OperationalState",
    "PolicyDecision",
    "PolicyEnvironment",
    "PolicyOutcome",
    "PolicyProfile",
    "PolicyRule",
    "ScannerCoverage",
    "Visibility",
    "WarningMode",
    "is_operational_state",
    "is_visibility",
    "resolve_policy_profiles",
    "resolve_rule_conflicts",
]
