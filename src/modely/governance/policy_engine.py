"""Policy evaluation helpers for scan results and unified governance policy engine."""

from __future__ import annotations

import json
from typing import Any, Optional

from ..domain.policies import (
    POLICY_ENVIRONMENTS,
    SCANNER_CATEGORIES,
    SCANNER_COVERAGE_STATUSES,
    PolicyDecision,
    PolicyProfile,
    PolicyRule,
    resolve_rule_conflicts,
)
from ..types import CatalogReport, ScanResult

_SEVERITY = {"low": 1, "medium": 2, "high": 3}


def _normalize_spdx(license_str: str) -> str:
    """Normalize an SPDX license identifier to lowercase and stripped.

    Examples::

        >>> _normalize_spdx("Apache-2.0")
        'apache-2.0'
        >>> _normalize_spdx("  MIT  ")
        'mit'
    """
    return license_str.strip().lower()


_SPDX_ALIASES = {
    "apache": "apache-2.0",
    "apache2": "apache-2.0",
    "apache 2.0": "apache-2.0",
    "gplv2": "gpl-2.0",
    "gplv3": "gpl-3.0",
    "gpl2": "gpl-2.0",
    "gpl3": "gpl-3.0",
    "lgplv2": "lgpl-2.1",
    "lgplv3": "lgpl-3.0",
    "bsd2": "bsd-2-clause",
    "bsd3": "bsd-3-clause",
    "cc-by": "cc-by-4.0",
    "cc0": "cc0-1.0",
    "public domain": "cc0-1.0",
}


def normalize_spdx(license_str: str) -> str:
    """Public-facing SPDX normalization with alias resolution.

    Falls back to lowercase stripped if no alias match.
    """
    normalized = _normalize_spdx(license_str)
    return _SPDX_ALIASES.get(normalized, normalized)


# ── License risk classification ────────────────────────────────────────────

_LICENSE_RISK = {
    "apache-2.0": "low",
    "mit": "low",
    "bsd-2-clause": "low",
    "bsd-3-clause": "low",
    "unlicense": "low",
    "cc0-1.0": "low",
    "mpl-2.0": "medium",
    "lgpl-2.1": "medium",
    "lgpl-3.0": "medium",
    "cc-by-4.0": "medium",
    "cc-by-nc-4.0": "medium",
    "gpl-2.0": "high",
    "gpl-3.0": "high",
    "agpl-3.0": "high",
    "unknown": "high",
    "other": "high",
}

_COPYLEFT_LICENSES = {
    "gpl-2.0",
    "gpl-3.0",
    "agpl-3.0",
    "lgpl-2.1",
    "lgpl-3.0",
    "mpl-2.0",
}

_COMMERCIAL_RISK_LICENSES = {
    "cc-by-nc-4.0",
    "gpl-3.0",
    "agpl-3.0",
}


def license_risk_level(license_id: str) -> str:
    """Return the risk level for a normalized SPDX license identifier."""
    return _LICENSE_RISK.get(normalize_spdx(license_id), "medium")


def is_copyleft(license_id: str) -> bool:
    """Return True if the license is a copyleft or reciprocal license."""
    return normalize_spdx(license_id) in _COPYLEFT_LICENSES


def has_commercial_risk(license_id: str) -> bool:
    """Return True if the license poses commercial-use risk."""
    return normalize_spdx(license_id) in _COMMERCIAL_RISK_LICENSES


# ── Multi-license handling ──────────────────────────────────────────────────

def resolve_multi_license_and(licenses: list[str]) -> dict[str, Any]:
    """Resolve a multi-license AND combination (all must be satisfied).

    AND semantics: the most restrictive license wins.
    """
    normalized = [normalize_spdx(lic) for lic in licenses]
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    highest_risk = "low"
    highest_risk_lic = normalized[0] if normalized else "unknown"
    for lic in normalized:
        r = license_risk_level(lic)
        if risk_order.get(r, 0) > risk_order.get(highest_risk, 0):
            highest_risk = r
            highest_risk_lic = lic
    return {
        "licenses": normalized,
        "combination": "AND",
        "effective": highest_risk_lic,
        "risk_level": highest_risk,
        "is_copyleft": is_copyleft(highest_risk_lic),
        "has_commercial_risk": has_commercial_risk(highest_risk_lic),
    }


def resolve_multi_license_or(licenses: list[str]) -> dict[str, Any]:
    """Resolve a multi-license OR combination (user may choose).

    OR semantics: the least restrictive license wins.
    """
    normalized = [normalize_spdx(lic) for lic in licenses]
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    lowest_risk = "high"
    lowest_risk_lic = normalized[0] if normalized else "unknown"
    for lic in normalized:
        r = license_risk_level(lic)
        if risk_order.get(r, 9) < risk_order.get(lowest_risk, 9):
            lowest_risk = r
            lowest_risk_lic = lic
    return {
        "licenses": normalized,
        "combination": "OR",
        "effective": lowest_risk_lic,
        "risk_level": lowest_risk,
        "is_copyleft": is_copyleft(lowest_risk_lic),
        "has_commercial_risk": has_commercial_risk(lowest_risk_lic),
    }


def resolve_multi_license(licenses: list[str], combination: str = "AND") -> dict[str, Any]:
    """Resolve a multi-license expression (AND or OR combination)."""
    if not licenses:
        return {
            "licenses": [],
            "combination": combination,
            "effective": "unknown",
            "risk_level": "high",
            "is_copyleft": False,
            "has_commercial_risk": False,
        }
    if len(licenses) == 1:
        lic = normalize_spdx(licenses[0])
        return {
            "licenses": [lic],
            "combination": "single",
            "effective": lic,
            "risk_level": license_risk_level(lic),
            "is_copyleft": is_copyleft(lic),
            "has_commercial_risk": has_commercial_risk(lic),
        }
    if combination.upper() == "OR":
        return resolve_multi_license_or(licenses)
    return resolve_multi_license_and(licenses)


# ── License policy evaluation from YAML/JSON rules ─────────────────────────

def evaluate_license_rules(
    licenses: list[str],
    license_rules: list[dict[str, Any]],
    *,
    combination: str = "AND",
) -> dict[str, Any]:
    """Evaluate a set of license rules against one or more license identifiers.

    Returns a dict with ``action``, matched rule IDs, and explanation.
    """
    normalized = [normalize_spdx(lic) for lic in licenses]
    matched_rules: list[str] = []
    blocked_licenses: list[str] = []
    warned_licenses: list[str] = []
    required_approval_licenses: list[str] = []

    for rule in license_rules:
        rule_id = rule.get("id", "")
        action = rule.get("action", "allow")
        match_licenses = {normalize_spdx(l) for l in rule.get("match", {}).get("licenses", [])}

        if not match_licenses:
            continue

        # Handle "unknown" special case
        if "unknown" in match_licenses and any(lic in {"unknown", "", "other"} for lic in normalized):
            matched_rules.append(rule_id)
            if action == "block":
                blocked_licenses.append("unknown")
            elif action == "warn":
                warned_licenses.append("unknown")
            elif action == "require_approval":
                required_approval_licenses.append("unknown")
            continue

        for lic in normalized:
            if lic in match_licenses:
                matched_rules.append(rule_id)
                if action == "block":
                    blocked_licenses.append(lic)
                elif action == "warn":
                    warned_licenses.append(lic)
                elif action == "require_approval":
                    required_approval_licenses.append(lic)

    multi = resolve_multi_license(licenses, combination)

    # Determine final action with precedence: block > require_approval > warn > allow
    if blocked_licenses:
        action = "block"
    elif required_approval_licenses:
        action = "require_approval"
    elif warned_licenses:
        action = "warn"
    else:
        action = "allow"

    return {
        "action": action,
        "normalized_licenses": normalized,
        "matched_rule_ids": matched_rules,
        "blocked_licenses": blocked_licenses,
        "warned_licenses": warned_licenses,
        "required_approval_licenses": required_approval_licenses,
        "multi_license": multi,
    }


# ── YAML/JSON policy profile loading ────────────────────────────────────────

def parse_policy_rules_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse policy rules from a YAML-sourced config dict.

    Supports the built-in YAML policy template format:

    .. code-block:: yaml

        license:
          allow:
            - Apache-2.0
            - MIT
          warn:
            - CC-BY-NC-4.0
          block:
            - GPL-3.0
            - AGPL-3.0
            - unknown
    """
    rules: list[dict[str, Any]] = []
    for category in SCANNER_CATEGORIES:
        cat_config = config.get(category, {})
        if not cat_config or not isinstance(cat_config, dict):
            continue
        for action in ("allow", "warn", "require_approval", "block"):
            items = cat_config.get(action, [])
            if not items:
                continue
            if isinstance(items, bool):
                items = []
            if isinstance(items, str):
                items = [items]
            rule = {
                "id": f"{category}-{action}",
                "category": category,
                "action": action,
                "match": {"licenses": [str(item) for item in items]} if action != "block" or category == "license" else {"finding_ids": [str(item) for item in items]},
                "description": f"Auto-generated {action} rule for {category}",
            }
            rules.append(rule)
    return rules


_POLICY_TEMPLATES = {
    "permissive": {
        "fail_on": "high",
        "deny_sources": [],
        "deny_licenses": [],
        "ignore_finding_ids": [],
    },
    "balanced": {
        "fail_on": "medium",
        "deny_licenses": ["unknown", "other"],
        "deny_finding_ids": ["pickle-artifact", "remote-code"],
        "min_score": 60,
    },
    "strict": {
        "fail_on": "low",
        "allow_licenses": ["apache-2.0", "mit", "bsd-3-clause"],
        "deny_finding_ids": ["pickle-artifact", "remote-code", "missing-license"],
        "require_checksums": True,
        "min_score": 80,
    },
}


def policy_template(name: str = "balanced") -> dict:
    """Return a built-in policy template."""
    if name not in _POLICY_TEMPLATES:
        raise ValueError(f"Unknown policy template: {name}")
    return json.loads(json.dumps(_POLICY_TEMPLATES[name]))


def write_policy_template(name: str, output: Optional[str] = None) -> dict:
    """Write or return a built-in policy template."""
    template = policy_template(name)
    if output:
        with open(output, "w") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
    return template


def load_policy(path: Optional[str]) -> dict:
    """Load a JSON policy file, returning an empty policy for None."""
    if not path:
        return {}
    with open(path, "r") as f:
        return json.load(f)


def evaluate_scan_policy(scan: ScanResult, *, fail_on: Optional[str] = None, policy: Optional[dict] = None) -> dict:
    """Evaluate a scan result against severity and finding/license policy."""
    policy = policy or {}
    threshold = fail_on or policy.get("fail_on")
    ignored_ids = set(policy.get("ignore_finding_ids") or [])
    deny_ids = set(policy.get("deny_finding_ids") or [])
    allow_licenses = {str(v).lower() for v in (policy.get("allow_licenses") or [])}
    deny_licenses = {str(v).lower() for v in (policy.get("deny_licenses") or [])}
    deny_sources = {str(v).lower() for v in (policy.get("deny_sources") or [])}
    require_checksums = bool(policy.get("require_checksums"))
    min_score = policy.get("min_score")
    violations = []
    ignored = []

    for finding in scan.findings:
        item = finding.to_dict()
        if finding.id in ignored_ids:
            ignored.append(item)
            continue
        if threshold and _SEVERITY.get(finding.severity, 0) >= _SEVERITY.get(threshold, 0):
            violations.append({"type": "severity", "finding": item, "threshold": threshold})
        if finding.id in deny_ids:
            violations.append({"type": "deny_finding", "finding": item})

    license_name = (scan.analysis.info.license if scan.analysis and scan.analysis.info else None) or ""
    if allow_licenses and license_name.lower() not in allow_licenses:
        violations.append({"type": "license", "license": license_name, "allowed": sorted(allow_licenses)})
    if deny_licenses and license_name.lower() in deny_licenses:
        violations.append({"type": "deny_license", "license": license_name})
    source = (scan.analysis.info.source if scan.analysis and scan.analysis.info else "").lower()
    if deny_sources and source in deny_sources:
        violations.append({"type": "deny_source", "source": source})
    if require_checksums and scan.analysis and any(not f.sha256 for f in (scan.analysis.files or [])):
        violations.append({"type": "require_checksums"})
    score_value = (scan.metadata or {}).get("score")
    if min_score is not None and score_value is not None and score_value < min_score:
        violations.append({"type": "min_score", "score": score_value, "minimum": min_score})

    return {
        "ok": not violations,
        "fail_on": threshold,
        "violations": violations,
        "ignored": ignored,
    }


def evaluate_catalog_policy(report: CatalogReport, *, fail_on: Optional[str] = None, policy: Optional[dict] = None) -> dict:
    """Evaluate catalog entry scan summaries against policy."""
    policy = policy or {}
    threshold = fail_on or policy.get("fail_on")
    ignored_ids = set(policy.get("ignore_finding_ids") or [])
    deny_ids = set(policy.get("deny_finding_ids") or [])
    deny_sources = {str(v).lower() for v in (policy.get("deny_sources") or [])}
    min_score = policy.get("min_score")
    blocked = []
    allowed = []
    for entry in report.entries:
        scan = entry.scan or {}
        finding_ids = [fid for fid in scan.get("finding_ids", []) if fid not in ignored_ids]
        risk = _risk_from_finding_ids(finding_ids, scan.get("risk_level") or "none")
        violations = []
        if threshold and _SEVERITY.get(risk, 0) >= _SEVERITY.get(threshold, 0):
            violations.append({"type": "severity", "risk_level": risk, "threshold": threshold})
        for fid in finding_ids:
            if fid in deny_ids:
                violations.append({"type": "deny_finding", "finding_id": fid})
        if deny_sources and (entry.source or "").lower() in deny_sources:
            violations.append({"type": "deny_source", "source": entry.source})
        score_value = (entry.score or {}).get("score") if isinstance(entry.score, dict) else None
        if min_score is not None and score_value is not None and score_value < min_score:
            violations.append({"type": "min_score", "score": score_value, "minimum": min_score})
        item = {"id": entry.id, "repo_id": entry.repo_id, "local_path": entry.local_path, "risk_level": risk, "finding_ids": finding_ids, "violations": violations}
        if violations:
            blocked.append(item)
        else:
            allowed.append(item)
    return {"ok": not blocked, "fail_on": threshold, "blocked": blocked, "allowed": allowed, "summary": {"blocked": len(blocked), "allowed": len(allowed)}}


def _risk_from_finding_ids(finding_ids: list[str], fallback: str) -> str:
    if not finding_ids:
        return "none"
    if fallback == "high":
        return "high"
    if any(fid in {"missing-license", "pickle-artifact"} for fid in finding_ids):
        return "high"
    if any(fid in {"missing-card", "missing-config", "unsafe-weight-format", "remote-code", "large-weights", "missing-file-list"} for fid in finding_ids):
        return "medium"
    return fallback if fallback in _SEVERITY else "low"


def print_catalog_policy_result(result: dict, *, as_json: bool = False) -> None:
    """Print catalog policy gate results."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Status:  {'ok' if result['ok'] else 'failed'}")
    print(f"Blocked: {result['summary']['blocked']}")
    print(f"Allowed: {result['summary']['allowed']}")
    if result["blocked"]:
        print("Blocked assets:")
        for item in result["blocked"]:
            label = item.get("repo_id") or item.get("id") or item.get("local_path")
            reasons = ", ".join(v["type"] for v in item["violations"])
            print(f"  - {label}: {reasons}")


# ── Unified governance policy evaluation engine ────────────────────────────

def _determine_scanner_coverage(
    scan_evidence: dict[str, Any],
    approvals_state: dict[str, Any],
) -> dict[str, str]:
    """Determine scanner coverage status for each scanner category.

    Returns a mapping of scanner_category -> coverage_status.
    Coverage statuses: full, partial, metadata_only, missing_evidence,
    not_configured, not_applicable, failed
    """
    coverage: dict[str, str] = {}
    evidence_map = scan_evidence if isinstance(scan_evidence, dict) else {}
    for category in SCANNER_CATEGORIES:
        scanner_data = evidence_map.get(category)
        if scanner_data is None:
            coverage[category] = "not_configured"
        elif isinstance(scanner_data, dict):
            status = scanner_data.get("status", "")
            if status == "failed":
                coverage[category] = "failed"
            elif status == "not_applicable":
                coverage[category] = "not_applicable"
            elif scanner_data.get("findings"):
                findings_count = len(scanner_data["findings"])
                total_expected = scanner_data.get("total_expected", findings_count)
                if findings_count > 0 and total_expected > 0:
                    coverage[category] = "full" if findings_count >= total_expected else "partial"
                else:
                    coverage[category] = "metadata_only"
            else:
                coverage[category] = "metadata_only"
        elif scanner_data is False:
            coverage[category] = "not_applicable"
        else:
            coverage[category] = "missing_evidence"

    # Check approval-state evidence as a secondary source
    approved_scanners = approvals_state.get("scanners_approved", []) if isinstance(approvals_state, dict) else []
    upgradable = {"missing_evidence", "metadata_only", "not_configured"}
    for cat in approved_scanners:
        if cat in coverage and coverage[cat] in upgradable:
            coverage[cat] = "partial"  # approval implies some evidence exists

    return coverage


def _collect_missing_evidence(
    scanner_coverage: dict[str, str],
    minimum_coverage: frozenset[str] | None = None,
) -> list[str]:
    """Collect scanner categories with missing or insufficient evidence.

    Categories with coverage status ``missing_evidence`` or ``not_configured`` are
    collected.  A minimum-required set can be passed; any category in that set that
    is missing will also be collected.
    """
    missing: list[str] = []
    required = minimum_coverage or frozenset()
    for category, status in scanner_coverage.items():
        if status in ("missing_evidence", "not_configured"):
            missing.append(category)
        elif category in required and status not in ("full", "partial"):
            missing.append(category)
    return missing


def evaluate_governance_policy(
    principal: dict[str, Any] | None = None,
    tenant_scope: dict[str, Any] | None = None,
    asset: dict[str, Any] | None = None,
    action: str = "",
    scan_evidence: dict[str, Any] | None = None,
    approval_state: dict[str, Any] | None = None,
    environment: str = "prod",
    source: str = "",
    request_context: dict[str, Any] | None = None,
    *,
    policy_profile: PolicyProfile | None = None,
) -> PolicyDecision:
    """Evaluate all governance policies and return a unified PolicyDecision.

    This is the central policy evaluation entry-point.  It consumes scan evidence,
    approval state, and the resolved policy profile to produce a single decision.

    Parameters
    ----------
    principal:
        The requesting user or service account identity dict.
        Expected keys: ``id``, ``username``, ``department``, ``service_account``.
    tenant_scope:
        Tenant scope dict: ``organization_id``, ``workspace_id``,
        optional ``project_id``, ``environment_id``.
    asset:
        The asset being evaluated.  Expected keys: ``repo_id``, ``repo_type``,
        ``source``, ``license``, ``tags``, ``files``.
    action:
        The requested action (e.g. ``asset:download``, ``asset:sync``).
    scan_evidence:
        Scanner outputs keyed by category (``license``, ``secret``,
        ``remote_code``, ``dataset_compliance``, etc.).  Each value is a dict
        with ``status``, ``findings``, ``total_expected``, etc.
    approval_state:
        Current approval state for this asset/principal pair.
        Expected keys: ``status``, ``reviewers``, ``scanners_approved``.
    environment:
        Target environment: ``dev``, ``staging``, ``prod``,
        ``training``, ``inference``.
    source:
        Asset source: ``hf``, ``ms``, ``github``, ``kaggle``, etc.
    request_context:
        Optional additional context (CLI flags, API headers, time-of-check).
    policy_profile:
        Resolved active PolicyProfile.  If ``None``, a default permissive
        decision is returned.

    Returns
    -------
    PolicyDecision
        A decision with ``outcome``, ``matched_rule_ids``, ``policy_version``,
        ``evidence_refs``, ``missing_evidence``, ``explanation``,
        ``scanner_coverage``, and all standard PolicyDecision fields.
    """
    request_context = request_context or {}
    scan_evidence = scan_evidence or {}
    approval_state = approval_state or {}
    asset = asset or {}

    # Determine scanner coverage
    scanner_coverage = _determine_scanner_coverage(scan_evidence, approval_state)
    missing_evidence = _collect_missing_evidence(scanner_coverage)

    # No profile -> default permissive
    if policy_profile is None:
        fallback_metadata: dict[str, Any] = dict(request_context)
        if principal and isinstance(principal, dict):
            fallback_metadata.setdefault("principal_id", principal.get("id", ""))
        fallback_metadata.setdefault("action", action)
        fallback_metadata.setdefault("environment", environment)
        return PolicyDecision(
            outcome="allow",
            reasons=["No policy profile resolved; default permissive"],
            risk_level="unknown",
            matched_rule_ids=[],
            policy_version="",
            evidence_refs={},
            missing_evidence=missing_evidence,
            explanation="No active policy profile was resolved for this request. Falling back to permissive allow.",
            scanner_coverage=scanner_coverage,
            metadata=fallback_metadata,
        )

    rules = resolve_rule_conflicts(policy_profile.rules)
    matched_rule_ids: list[str] = []
    blocked_reasons: list[str] = []
    approval_reasons: list[str] = []
    warn_reasons: list[str] = []
    finding_ids: list[str] = []
    remediation_hints: list[str] = []
    evidence_refs: dict[str, str] = {}
    highest_risk = "unknown"

    # ── License evaluation ────────────────────────────────────────────
    license_raw = asset.get("license", "")
    licenses = [license_raw] if license_raw else []
    multi_license_key = request_context.get("license_combination", "AND")
    license_rules = [r for r in rules if r.category == "license"]
    if license_rules:
        license_rules_dicts = [
            {"id": r.id, "category": r.category, "action": r.action, "match": r.match, "description": r.description}
            for r in license_rules
        ]
        lic_result = evaluate_license_rules(licenses, license_rules_dicts, combination=multi_license_key)
        lic_action = lic_result["action"]
        if lic_action == "block":
            blocked_reasons.append(f"License {lic_result['blocked_licenses']} is blocked by policy")
        elif lic_action == "require_approval":
            approval_reasons.append(f"License {lic_result['required_approval_licenses']} requires approval")
        elif lic_action == "warn":
            warn_reasons.append(f"License {lic_result['warned_licenses']} triggers a warning")
        matched_rule_ids.extend(lic_result["matched_rule_ids"])
        multi = lic_result["multi_license"]
        evidence_refs["license"] = (
            f"resolved:{multi['effective']} risk:{multi['risk_level']} "
            f"copyleft:{multi['is_copyleft']} commercial_risk:{multi['has_commercial_risk']}"
        )
        risk_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        multi_risk = risk_map.get(multi["risk_level"], 2)
        if multi_risk > risk_map.get(highest_risk, 0):
            highest_risk = multi["risk_level"]

        # Collect finding IDs from unknown/missing license
        if "unknown" in licenses or not licenses:
            finding_ids.append("missing-license")

    # ── Secret evaluation ─────────────────────────────────────────────
    secret_rules = [r for r in rules if r.category == "secret"]
    secret_evidence = scan_evidence.get("secret", {})
    secret_findings = secret_evidence.get("findings", []) if isinstance(secret_evidence, dict) else []
    if secret_rules and secret_findings:
        for rule in secret_rules:
            rule_action = rule.action
            for finding in secret_findings:
                if isinstance(finding, dict):
                    fid = finding.get("id", "")
                    fids = rule.match.get("finding_ids", [])
                    if fid in fids or "*" in fids:
                        matched_rule_ids.append(rule.id)
                        finding_ids.append(fid)
                        if rule_action == "block":
                            blocked_reasons.append(f"Secret finding {fid}: blocked by policy")
                        elif rule_action == "require_approval":
                            approval_reasons.append(f"Secret finding {fid}: requires approval")
                        elif rule_action == "warn":
                            warn_reasons.append(f"Secret finding {fid}: warning")
                elif isinstance(finding, str):
                    fids = rule.match.get("finding_ids", [])
                    if finding in fids or "*" in fids:
                        matched_rule_ids.append(rule.id)
                        finding_ids.append(finding)
                        if rule_action == "block":
                            blocked_reasons.append(f"Secret finding {finding}: blocked by policy")
                        elif rule_action == "require_approval":
                            approval_reasons.append(f"Secret finding {finding}: requires approval")
                        elif rule_action == "warn":
                            warn_reasons.append(f"Secret finding {finding}: warning")

    # ── Remote-code evaluation ─────────────────────────────────────────
    remote_rules = [r for r in rules if r.category == "remote_code"]
    remote_evidence = scan_evidence.get("remote_code", {})
    remote_findings = remote_evidence.get("findings", []) if isinstance(remote_evidence, dict) else []
    if remote_rules and remote_findings:
        for rule in remote_rules:
            rule_action = rule.action
            for finding in remote_findings:
                if isinstance(finding, dict):
                    fid = finding.get("id", "")
                    sev = finding.get("severity", "medium")
                    fids = rule.match.get("finding_ids", [])
                    if fid in fids:
                        matched_rule_ids.append(rule.id)
                        finding_ids.append(fid)
                        if rule_action == "block":
                            blocked_reasons.append(f"Remote-code finding {fid}: blocked by policy")
                        elif rule_action == "require_approval":
                            approval_reasons.append(f"Remote-code finding {fid}: requires approval")
                        elif rule_action == "warn":
                            warn_reasons.append(f"Remote-code finding {fid}: warning")
                    if any(high_id in fids for high_id in ("pickle-artifact", "remote-code", "executable")):
                        highest_risk = "high"
                elif isinstance(finding, str):
                    fids = rule.match.get("finding_ids", [])
                    if finding in fids:
                        matched_rule_ids.append(rule.id)
                        finding_ids.append(finding)
                        if rule_action == "block":
                            blocked_reasons.append(f"Remote-code finding {finding}: blocked by policy")

    # ── Dataset compliance evaluation ──────────────────────────────────
    dataset_rules = [r for r in rules if r.category == "dataset_compliance"]
    dataset_evidence = scan_evidence.get("dataset_compliance", {})
    dataset_findings = dataset_evidence.get("findings", []) if isinstance(dataset_evidence, dict) else []
    if dataset_rules and dataset_findings:
        for rule in dataset_rules:
            rule_action = rule.action
            for finding in dataset_findings:
                if isinstance(finding, dict):
                    fid = finding.get("id", "")
                    fids = rule.match.get("finding_ids", [])
                    if fid in fids:
                        matched_rule_ids.append(rule.id)
                        finding_ids.append(fid)
                        if rule_action == "block":
                            blocked_reasons.append(f"Dataset finding {fid}: blocked by policy")
                        elif rule_action == "require_approval":
                            approval_reasons.append(f"Dataset finding {fid}: requires approval")
                        elif rule_action == "warn":
                            warn_reasons.append(f"Dataset finding {fid}: warning")
                elif isinstance(finding, str):
                    fids = rule.match.get("finding_ids", [])
                    if finding in fids:
                        matched_rule_ids.append(rule.id)
                        finding_ids.append(finding)
                        if rule_action == "block":
                            blocked_reasons.append(f"Dataset finding {finding}: blocked by policy")

    # ── Collect evidence refs from scan evidence ─────────────────────
    for cat, ev in scan_evidence.items():
        if isinstance(ev, dict) and ev.get("ref"):
            evidence_refs[cat] = str(ev["ref"])
        elif isinstance(ev, dict):
            evidence_refs[cat] = f"coverage:{scanner_coverage.get(cat, 'unknown')}"

    # ── Apply approval state ───────────────────────────────────────────
    approval_status = approval_state.get("status", "none") if isinstance(approval_state, dict) else "none"
    if approval_status == "approved" and not blocked_reasons:
        # Approval overrides warn/require_approval but not block
        pass  # decision stays as per rules below
    elif approval_status == "rejected":
        blocked_reasons.append("Asset access was explicitly rejected by an approver")

    # ── Build final decision ───────────────────────────────────────────
    # Precedence: block > require_approval > warn > allow
    if blocked_reasons:
        outcome = "block"
        reasons = blocked_reasons
    elif approval_reasons and approval_status not in ("approved",):
        outcome = "require_approval"
        reasons = approval_reasons
    elif warn_reasons:
        outcome = "warn"
        reasons = warn_reasons
    else:
        outcome = "allow"
        reasons = ["No policy violations detected"]

    # Handle approval_status == "approved" with only warn_reasons
    if approval_status == "approved" and not blocked_reasons and not approval_reasons:
        if warn_reasons:
            outcome = "warn"
            reasons = warn_reasons
        else:
            outcome = "allow"
            reasons = ["Asset access approved; no blocking policy violations"]

    # Build explanation
    explanation_parts = [
        f"Environment: {environment}",
        f"Source: {source}",
        f"Action: {action}",
        f"Policy profile: {policy_profile.name} v{policy_profile.version}",
    ]
    if blocked_reasons:
        explanation_parts.append(f"Blocked: {'; '.join(blocked_reasons)}")
    elif approval_reasons:
        explanation_parts.append(f"Approval required: {'; '.join(approval_reasons)}")
    elif warn_reasons:
        explanation_parts.append(f"Warnings: {'; '.join(warn_reasons)}")
    if missing_evidence:
        explanation_parts.append(f"Missing evidence for: {', '.join(missing_evidence)}")

    # Merge request_context and principal info into metadata for audit/compliance
    decision_metadata: dict[str, Any] = dict(request_context)
    if isinstance(principal, dict):
        for key in ("id", "username", "department", "service_account", "display_name", "email"):
            if key in principal:
                decision_metadata[f"principal_{key}"] = principal[key]
    if principal and isinstance(principal, dict):
        decision_metadata.setdefault("principal_id", principal.get("id", ""))
        decision_metadata.setdefault("username", principal.get("username", ""))
    if asset and isinstance(asset, dict):
        decision_metadata.setdefault("asset_id", asset.get("id", asset.get("repo_id", "")))
    decision_metadata.setdefault("action", action)
    decision_metadata.setdefault("environment", environment)
    decision_metadata.setdefault("source", source)

    # ── Audit: policy.evaluated ─────────────────────────────────────────────
    # Emit after the decision is fully built so the event captures the outcome
    # and matched rule ids.  Uses a lazy import to avoid circular dependencies.
    from .audit import emit_audit_event
    from ..domain.audit_events import AUDIT_POLICY_EVALUATED

    audit_resource = (
        asset.get("repo_id") or asset.get("id") or "unknown"
    ) if isinstance(asset, dict) else "unknown"

    audit_metadata: dict[str, Any] = {
        "outcome": outcome,
        "risk_level": highest_risk,
        "policy_profile": policy_profile.name if policy_profile else "default",
        "policy_version": policy_profile.version if policy_profile else "",
        "matched_rule_ids": matched_rule_ids,
        "finding_ids": finding_ids,
        "action": action,
        "environment": environment,
        "source": source,
    }
    if missing_evidence:
        audit_metadata["missing_evidence"] = missing_evidence

    emit_audit_event(
        AUDIT_POLICY_EVALUATED,
        resource=audit_resource,
        status="ok" if outcome in ("allow", "warn") else "denied",
        actor=(
            principal.get("id") or principal.get("principal_id")
        ) if isinstance(principal, dict) else None,
        metadata=audit_metadata,
        tenant_scope=(
            tenant_scope
            if isinstance(tenant_scope, dict)
            else (
                tenant_scope.to_dict()
                if hasattr(tenant_scope, "to_dict")
                else None
            )
        ),
    )

    return PolicyDecision(
        outcome=outcome,
        reasons=reasons,
        risk_level=highest_risk,
        finding_ids=finding_ids,
        remediation_hints=remediation_hints,
        matched_rule_ids=matched_rule_ids,
        policy_version=policy_profile.version,
        evidence_refs=evidence_refs,
        missing_evidence=missing_evidence,
        explanation="; ".join(explanation_parts),
        scanner_coverage=scanner_coverage,
        metadata=decision_metadata,
    )


__all__ = [
    "policy_template",
    "write_policy_template",
    "load_policy",
    "evaluate_scan_policy",
    "evaluate_catalog_policy",
    "print_catalog_policy_result",
    "normalize_spdx",
    "evaluate_license_rules",
    "evaluate_governance_policy",
    "license_risk_level",
    "is_copyleft",
    "has_commercial_risk",
    "resolve_multi_license",
    "resolve_multi_license_and",
    "resolve_multi_license_or",
    "parse_policy_rules_from_config",
]
