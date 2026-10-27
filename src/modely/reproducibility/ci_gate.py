"""CI gate decision helpers — Phase 3b implementation.

Evaluates a lockfile against policy, generating deterministic pass/fail
with JSON/Markdown/SARIF-compatible output and stable exit codes.
"""

from __future__ import annotations

from ..governance.policy_engine import evaluate_scan_policy, load_policy
from ..reporting.json import format_json as _format_json
from ..reporting.markdown import format_markdown as _format_markdown
from ..reporting.sarif import format_sarif as _format_sarif
from .lockfiles import read_enterprise_lock, validate_enterprise_lock

# Stable exit codes per docs/specs/enterprise-cli.md
EXIT_PASS = 0
EXIT_WARN = 10
EXIT_BLOCKED = 12
EXIT_CHECKSUM_MISMATCH = 13
EXIT_ERROR = 1

# Pre-defined profiles
_PROFILES = {
    "production": {"fail_on": "high", "require_checksums": True, "deny_licenses": ["unlicensed"]},
    "staging": {"fail_on": "critical"},
    "dev": {},
}


def evaluate_ci_gate(
    lockfile_path: str,
    *,
    profile: str = "production",
    fail_on_warnings: bool = False,
    policy_path: str | None = None,
) -> dict:
    """Evaluate a lockfile against policy for CI gate decisions.

    Returns a structured result with per-resource status and a summary.
    Maps to stable exit codes defined in enterprise-cli.md.
    """

    # Step 1: Validate lockfile integrity (checksums, snapshot refs)
    validation = validate_enterprise_lock(
        path=lockfile_path, profile=profile, fail_on_warnings=fail_on_warnings,
    )

    # Step 2: Load profile-specific policy
    profile_policy = _PROFILES.get(profile, _PROFILES["production"])
    if policy_path:
        user_policy = load_policy(policy_path)
        profile_policy = {**profile_policy, **user_policy}

    # Step 3: Evaluate each resource against governance policy
    resources = []
    overall_status = "passed"
    highest_exit = EXIT_PASS

    for res in validation.get("resources", []):
        res_status = "passed"
        res_errors = list(res.get("errors", []))
        res_warnings = list(res.get("warnings", []))

        # Checksum mismatch detection
        if not res.get("checksum_ok"):
            res_status = "failed"
            res_errors.append("Checksum validation failed")

        # Policy evaluation per resource
        if res.get("uri"):
            entry = _find_lockfile_entry(lockfile_path, res["uri"])
            if entry:
                # Check license against profile
                for lic in profile_policy.get("deny_licenses", []):
                    if entry.get("license", "").lower() == lic.lower():
                        res_status = "failed"
                        res_errors.append(f"Blocked license: {lic}")

                # Check if policy is blocked
                if entry.get("policy_status") == "blocked":
                    res_status = "failed"
                    res_errors.append(f"Policy blocks resource: {res['uri']}")

        # Missing snapshot ref
        if not res.get("snapshot_ref_valid"):
            if profile in ("production",):
                res_status = "failed"
                res_errors.append("Missing approved snapshot ref (required for production)")
            else:
                res_warnings.append("Missing approved snapshot ref")

        if res_status == "failed":
            overall_status = "failed"
            highest_exit = EXIT_BLOCKED
        elif res_warnings and fail_on_warnings:
            res_status = "failed"
            overall_status = "failed"
            highest_exit = EXIT_WARN
        elif res_warnings:
            res_status = "warning"
            if overall_status != "failed":
                overall_status = "warning"
                highest_exit = EXIT_WARN

        resources.append({
            "uri": res.get("uri", ""),
            "status": res_status,
            "errors": res_errors,
            "warnings": res_warnings,
            "checksum_ok": res.get("checksum_ok", True),
            "policy_ok": res.get("policy_ok", True),
            "approval_ok": res.get("approval_ok", True),
        })

    return {
        "status": overall_status,
        "exit_code": highest_exit,
        "profile": profile,
        "lockfile_path": lockfile_path,
        "resources": resources,
        "summary": {
            "total": len(resources),
            "passed": sum(1 for r in resources if r["status"] == "passed"),
            "failed": sum(1 for r in resources if r["status"] == "failed"),
            "warning": sum(1 for r in resources if r["status"] == "warning"),
        },
        "validation": validation,
    }


def format_ci_result(result: dict, fmt: str = "json") -> str:
    """Format a CI gate result in the requested output format."""
    if fmt == "json":
        return _format_json(result)
    elif fmt == "markdown":
        return _format_markdown(result)
    elif fmt == "sarif":
        findings = []
        for r in result.get("resources", []):
            if r["status"] != "passed":
                for err in r.get("errors", []):
                    findings.append({
                        "id": f"ci-gate/{r['uri']}",
                        "severity": "error" if r["status"] == "failed" else "warning",
                        "category": "governance",
                        "message": err,
                        "path": r["uri"],
                    })
        from ..types import ScanFinding
        sarif_findings = [
            ScanFinding(id=f["id"], severity=f["severity"], category=f["category"], message=f["message"], path=f["path"])
            for f in findings
        ]
        import json
        return json.dumps(_format_sarif(sarif_findings), indent=2)
    return _format_json(result)


def evaluate_lock_gate(validation: dict, *, fail_on_warnings: bool = False) -> dict:
    """(Legacy) Return a minimal CI-friendly decision from lock validation output."""
    warnings = []
    if validation.get("missing_checksums"):
        warnings.append("missing checksums")
    ok = bool(validation.get("ok")) and not (fail_on_warnings and warnings)
    return {"ok": ok, "status": "passed" if ok else "failed", "warnings": warnings, "validation": validation}


def _find_lockfile_entry(lockfile_path: str, uri: str) -> dict | None:
    """Find a lockfile entry by URI for policy evaluation."""
    try:
        lockfile = read_enterprise_lock(lockfile_path)
        for entry in lockfile.resources:
            if entry.uri == uri:
                return entry.to_dict()
    except Exception:
        pass
    return None


__all__ = [
    "EXIT_BLOCKED",
    "EXIT_CHECKSUM_MISMATCH",
    "EXIT_ERROR",
    "EXIT_PASS",
    "EXIT_WARN",
    "evaluate_ci_gate",
    "evaluate_lock_gate",
    "format_ci_result",
]
