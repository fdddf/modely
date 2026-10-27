"""SARIF-compatible report formatter integration point."""

from __future__ import annotations


def finding_to_sarif_result(finding) -> dict:
    """Convert a scan finding-like object to a minimal SARIF result."""
    rule_id = getattr(finding, "id", None) or finding.get("id", "modely-finding")
    message = getattr(finding, "message", None) or finding.get("message", "modely finding")
    path = getattr(finding, "path", None) or finding.get("path")
    result = {"ruleId": rule_id, "message": {"text": message}}
    if path:
        result["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": path}}}]
    return result


def format_sarif(findings) -> dict:
    """Build a minimal SARIF 2.1.0 payload from scan findings."""
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{"tool": {"driver": {"name": "modely-ai"}}, "results": [finding_to_sarif_result(f) for f in findings]}],
    }


__all__ = ["finding_to_sarif_result", "format_sarif"]
