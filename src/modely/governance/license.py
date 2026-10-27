"""License risk classification helpers."""

from __future__ import annotations

import json
from typing import Protocol


class LicenseRepoInfo(Protocol):
    """Repository metadata required for license risk classification."""

    source: str
    repo_type: str
    repo_id: str
    license: str | None


def classify_license(license_name: str | None) -> dict:
    """Classify license risk for resource governance."""
    value = (license_name or "").lower()
    if not value or value in {"unknown", "other", "none"}:
        return _risk("unknown", "high", "No clear license metadata detected.")
    if any(token in value for token in ("cc-by-nc", "non-commercial", "noncommercial", "research-only")):
        return _risk("non-commercial", "high", "License appears to restrict commercial use.")
    if any(token in value for token in ("agpl", "gpl-", "gpl_", "gpl ")):
        return _risk("strong-copyleft", "medium", "Strong copyleft obligations may affect redistribution.")
    if any(token in value for token in ("lgpl", "mpl", "epl")):
        return _risk("weak-copyleft", "medium", "Copyleft obligations may require review.")
    if any(token in value for token in ("llama", "openrail", "rail", "custom", "community")):
        return _risk("custom-restrictive", "medium", "Custom or responsible-AI license needs manual review.")
    if any(token in value for token in ("mit", "apache", "bsd", "isc", "cc-by", "unlicense")):
        return _risk("permissive", "low", "License appears permissive; still verify obligations.")
    return _risk("other", "medium", "License is recognized as other and should be reviewed.")


def build_license_risk(resource: str, info: LicenseRepoInfo) -> dict:
    """Build a license risk report from repository metadata."""
    result = classify_license(info.license)
    result.update({"resource": resource, "source": info.source, "repo_type": info.repo_type, "repo_id": info.repo_id, "license": info.license})
    return result


def print_license_risk(result: dict, *, as_json: bool = False) -> None:
    """Print license risk."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Repo:     {result.get('source')}:{result.get('repo_type')}:{result.get('repo_id')}")
    print(f"License:  {result.get('license') or '-'}")
    print(f"Class:    {result.get('class')}")
    print(f"Risk:     {result.get('risk')}")
    print(f"Reason:   {result.get('reason')}")


def _risk(klass: str, risk: str, reason: str) -> dict:
    return {"class": klass, "risk": risk, "reason": reason}


__all__ = ["classify_license", "build_license_risk", "print_license_risk"]
