"""Unit tests for policy evaluation."""

from modely.policy import evaluate_catalog_policy, evaluate_scan_policy
from modely.types import AssetAnalysis, CatalogEntry, CatalogReport, FileSummary, RepoInfo, ScanFinding, ScanResult


def _scan(findings, license="mit"):
    return ScanResult(
        "resource",
        "high" if any(f.severity == "high" for f in findings) else "low",
        findings=findings,
        analysis=AssetAnalysis(RepoInfo("hf", "model", "repo", license=license), FileSummary()),
    )


def test_fail_on_severity_threshold():
    result = evaluate_scan_policy(_scan([ScanFinding("x", "high", "security", "bad")]), fail_on="medium")

    assert result["ok"] is False
    assert result["violations"][0]["type"] == "severity"


def test_deny_and_ignore_finding_ids():
    scan = _scan([
        ScanFinding("remote-code", "medium", "security", "code"),
        ScanFinding("missing-checksums", "low", "reproducibility", "checksum"),
    ])

    result = evaluate_scan_policy(scan, policy={"deny_finding_ids": ["remote-code"], "ignore_finding_ids": ["missing-checksums"]})

    assert result["ok"] is False
    assert result["violations"][0]["type"] == "deny_finding"
    assert result["ignored"][0]["id"] == "missing-checksums"


def test_allowed_license_policy():
    result = evaluate_scan_policy(_scan([], license="unknown"), policy={"allow_licenses": ["mit", "apache-2.0"]})

    assert result["ok"] is False
    assert result["violations"][0]["type"] == "license"


def test_catalog_policy_blocks_scan_summary():
    report = CatalogReport("/tmp", entries=[
        CatalogEntry("bad", scan={"risk_level": "high", "finding_ids": ["pickle-artifact"]}),
        CatalogEntry("ok", scan={"risk_level": "low", "finding_ids": []}),
    ])

    result = evaluate_catalog_policy(report, fail_on="medium")

    assert result["ok"] is False
    assert result["summary"] == {"blocked": 1, "allowed": 1}
    assert result["blocked"][0]["id"] == "bad"


def test_catalog_policy_ignores_ids_before_threshold():
    report = CatalogReport("/tmp", entries=[CatalogEntry("ignored", scan={"risk_level": "high", "finding_ids": ["pickle-artifact"]})])

    result = evaluate_catalog_policy(report, fail_on="high", policy={"ignore_finding_ids": ["pickle-artifact"]})

    assert result["ok"] is True


def test_catalog_policy_preserves_unknown_high_risk_findings():
    report = CatalogReport("/tmp", entries=[CatalogEntry("bad", scan={"risk_level": "high", "finding_ids": ["malware-signature", "missing-card"]})])

    result = evaluate_catalog_policy(report, fail_on="high")

    assert result["ok"] is False
    assert result["blocked"][0]["risk_level"] == "high"
