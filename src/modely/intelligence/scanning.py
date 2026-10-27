"""Asset risk scanning implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from .analysis import analyze_resource
from ..cataloging.local_assets import analyze_local_path
from ..application.file_queries import format_file_size
from ..uri import parse_modely_uri
from ..types import AssetAnalysis, ScanFinding, ScanResult

_PICKLE_SUFFIXES = (".pkl", ".pickle", ".joblib")
_ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")
_SUSPICIOUS_CODE_PATTERNS = {
    "dynamic-exec": re.compile(r"\b(eval|exec)\s*\("),
    "subprocess-call": re.compile(r"\b(subprocess|os\.system|Popen|check_output|run)\b"),
    "network-call": re.compile(r"\b(requests\.|urllib\.|socket\.)"),
    "pickle-load": re.compile(r"\b(pickle|joblib)\.(load|loads)\b"),
    "dynamic-import": re.compile(r"\b(__import__|importlib\.import_module)\b"),
}
_MAX_CODE_SCAN_BYTES = 256_000
_RISKY_WEIGHT_SUFFIXES = (".pt", ".pth", ".bin", ".ckpt")
_CUSTOM_CODE_PREFIXES = ("modeling_", "configuration_", "tokenization_")
_SCRIPT_SUFFIXES = (".sh", ".bat", ".ps1")
_SECRET_PATTERNS = {
    "possible-token": re.compile(r"(?i)(hf_|ghp_|sk-[a-z0-9])"),
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
}
_SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def scan_resource(
    resource: str,
    *,
    revision: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    profile: Optional[str] = None,
    deep: bool = True,
    inspect_files: bool = False,
    source: str = "auto",
    repo_type: str = "auto",
    analyze_resource_func=None,
) -> ScanResult:
    """Scan a resource for metadata, safety, and reproducibility risks."""
    if analyze_resource_func is None:
        analyze_resource_func = analyze_resource
    analysis = analyze_resource_func(
        resource,
        revision=revision,
        token=token,
        endpoint=endpoint,
        include=include,
        exclude=exclude,
        profile=profile,
        deep=deep,
        source=source,
        repo_type=repo_type,
    )
    findings = find_scan_findings(analysis)
    if inspect_files:
        findings = _dedupe_findings(findings + _remote_content_findings(resource, analysis, revision=revision, token=token, endpoint=endpoint))
    return scan_analysis(
        resource,
        analysis,
        findings=findings,
        deep=deep,
        profile=profile,
        include=include,
        exclude=exclude,
        inspect_files=inspect_files,
    )


def scan_analysis(
    resource: str,
    analysis: AssetAnalysis,
    *,
    findings: Optional[list[ScanFinding]] = None,
    deep: bool = True,
    profile=None,
    include=None,
    exclude=None,
    inspect_files: bool = False,
) -> ScanResult:
    """Build a scan result from an existing asset analysis."""
    findings = find_scan_findings(analysis) if findings is None else findings
    return ScanResult(
        resource=resource,
        risk_level=risk_level(findings),
        findings=findings,
        summary=summarize_findings(findings),
        analysis=analysis,
        metadata={"deep": deep, "profile": profile, "include": include, "exclude": exclude, "content_inspected": inspect_files},
    )


def scan_path(path: str, *, deep: bool = True) -> ScanResult:
    """Scan a local path without network access."""
    analysis = analyze_local_path(path, deep=deep)
    findings = _dedupe_findings(find_scan_findings(analysis) + _local_content_findings(path))
    return ScanResult(
        resource=path,
        risk_level=risk_level(findings),
        findings=findings,
        summary=summarize_findings(findings),
        analysis=analysis,
        metadata={"deep": deep, "local": True, "content_inspected": True},
    )


def find_scan_findings(analysis: AssetAnalysis) -> list[ScanFinding]:
    """Return deterministic scan findings for an analyzed asset."""
    findings: list[ScanFinding] = []
    info = analysis.info

    if not info.license:
        findings.append(ScanFinding(
            "missing-license",
            "high",
            "compliance",
            "No license metadata detected.",
            recommendation="Confirm usage rights before using this asset commercially.",
        ))
    else:
        license_class = _license_class(info.license)
        if license_class in {"non-commercial", "strong-copyleft", "weak-copyleft", "custom-restrictive", "unknown"}:
            findings.append(ScanFinding(
                f"license-{license_class}",
                "medium" if license_class != "unknown" else "low",
                "compliance",
                f"License appears to be {license_class}.",
                recommendation="Evaluate license compatibility with your intended use.",
                metadata={"license": info.license, "class": license_class},
            ))
    if not analysis.has_card:
        findings.append(ScanFinding(
            "missing-card",
            "medium",
            "metadata",
            "No README/model card detected.",
            recommendation="Prefer assets with model cards that document intended use and limitations.",
        ))
    if not analysis.has_config:
        findings.append(ScanFinding(
            "missing-config",
            "medium",
            "completeness",
            "No config file detected.",
            recommendation="Verify the asset can be loaded by the intended framework.",
        ))
    if info.repo_type == "model" and not analysis.has_tokenizer:
        findings.append(ScanFinding(
            "missing-tokenizer",
            "low",
            "completeness",
            "No tokenizer file detected for this model.",
            recommendation="Check whether tokenizer assets are stored separately or are not required.",
        ))

    files = analysis.files or []
    if not files:
        findings.append(ScanFinding(
            "missing-file-list",
            "medium",
            "reproducibility",
            "No remote files were listed for this asset.",
            recommendation="Verify source permissions or backend file-listing support.",
        ))
    elif not any(f.sha256 for f in files):
        findings.append(ScanFinding(
            "missing-checksums",
            "low",
            "reproducibility",
            "No SHA256 metadata detected on listed files.",
            recommendation="Use source revisions and lockfiles; checksum validation may be unavailable.",
        ))

    for f in files:
        lower = f.path.lower()
        name = lower.rsplit("/", 1)[-1]
        if name in {".env", ".env.local", "credentials.json"} or "/.env" in lower:
            findings.append(ScanFinding(
                "secret-file",
                "high",
                "security",
                "Potential secret or credential file detected.",
                path=f.path,
                recommendation="Remove secrets from published assets and rotate exposed credentials.",
            ))
        if lower.endswith(_PICKLE_SUFFIXES):
            findings.append(ScanFinding(
                "pickle-artifact",
                "high",
                "security",
                "Pickle-like artifact may execute code when loaded.",
                path=f.path,
                recommendation="Avoid loading pickle artifacts from untrusted sources.",
            ))
        elif lower.endswith(_RISKY_WEIGHT_SUFFIXES):
            findings.append(ScanFinding(
                "unsafe-weight-format",
                "medium",
                "security",
                "Legacy weight format may execute code or be harder to inspect safely.",
                path=f.path,
                recommendation="Prefer safetensors when available.",
            ))

        if _is_custom_code_path(f.path):
            findings.append(ScanFinding(
                "remote-code",
                "medium",
                "security",
                "Custom Python code detected in the repository.",
                path=f.path,
                recommendation="Inspect code before enabling trust_remote_code or importing repository modules.",
            ))
        if name.endswith(_SCRIPT_SUFFIXES):
            findings.append(ScanFinding(
                "script-file",
                "low",
                "security",
                "Executable script detected in the repository.",
                path=f.path,
                recommendation="Review scripts before execution.",
            ))
        if lower.endswith(_ARCHIVE_SUFFIXES) and ("../" in lower or lower.startswith("/")):
            findings.append(ScanFinding(
                "archive-path-traversal",
                "high",
                "security",
                "Archive path suggests possible path traversal risk.",
                path=f.path,
                recommendation="Inspect archive contents before extraction.",
            ))

    deep = (analysis.metadata or {}).get("deep") or {}
    if "large-weights" in deep.get("risk_flags", []) or deep.get("weight_bytes", 0) >= 10_000_000_000:
        findings.append(ScanFinding(
            "large-weights",
            "medium",
            "operations",
            f"Large weight files detected ({format_file_size(deep.get('weight_bytes', 0))}).",
            recommendation="Use profiles, partial downloads, or sufficient local storage.",
        ))

    return _dedupe_findings(findings)


def risk_level(findings: list[ScanFinding]) -> str:
    """Return overall risk level for findings."""
    if any(f.severity == "high" for f in findings):
        return "high"
    if any(f.severity == "medium" for f in findings):
        return "medium"
    if any(f.severity == "low" for f in findings):
        return "low"
    return "none"


def summarize_findings(findings: list[ScanFinding]) -> dict[str, int]:
    """Summarize findings by severity."""
    summary = {"high": 0, "medium": 0, "low": 0, "total": len(findings)}
    for finding in findings:
        if finding.severity in summary:
            summary[finding.severity] += 1
    return summary


def print_scan_result(result: ScanResult, *, as_json: bool = False) -> None:
    """Print a scan result."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Resource:   {result.resource}")
    print(f"Risk level: {result.risk_level}")
    print(f"Findings:   {result.summary.get('total', 0)}")
    if not result.findings:
        print("No findings.")
        return
    print("Findings:")
    for finding in result.findings:
        location = f" ({finding.path})" if finding.path else ""
        print(f"  - [{finding.severity}] {finding.id}{location}: {finding.message}")
        if finding.recommendation:
            print(f"    Recommendation: {finding.recommendation}")


def _is_custom_code_path(path: str) -> bool:
    name = path.lower().rsplit("/", 1)[-1]
    if not name.endswith(".py"):
        return False
    if name.startswith(_CUSTOM_CODE_PREFIXES):
        return True
    return "/" not in path and name not in {"setup.py", "__init__.py"}


def _license_class(license_name: str) -> str:
    value = (license_name or "").lower()
    if not value or value in {"unknown", "other", "none"}:
        return "unknown"
    if any(token in value for token in ("cc-by-nc", "non-commercial", "noncommercial", "research-only")):
        return "non-commercial"
    if any(token in value for token in ("agpl", "gpl-", "gpl_", "gpl ")):
        return "strong-copyleft"
    if any(token in value for token in ("lgpl", "mpl", "epl")):
        return "weak-copyleft"
    if any(token in value for token in ("llama", "openrail", "rail", "qwen", "deepseek", "custom", "community")):
        return "custom-restrictive"
    if any(token in value for token in ("mit", "apache", "bsd", "isc", "cc-by", "unlicense")):
        return "permissive"
    return "other"


def _remote_content_findings(resource: str, analysis: AssetAnalysis, *, revision=None, token=None, endpoint=None) -> list[ScanFinding]:
    ref = parse_modely_uri(resource)
    findings = []
    inspected = 0
    for f in analysis.files or []:
        if inspected >= 20 or not _is_inspectable_path(f.path) or (f.size or 0) > _MAX_CODE_SCAN_BYTES:
            continue
        try:
            text = _fetch_small_text(ref, f.path, revision=revision, token=token, endpoint=endpoint)
        except Exception:
            continue
        if not text:
            continue
        inspected += 1
        findings.extend(_content_findings(text, f.path))
    return findings


def _fetch_small_text(ref, path: str, *, revision=None, token=None, endpoint=None) -> str:
    if ref.source == "hf":
        from huggingface_hub import hf_hub_download
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            local = hf_hub_download(ref.repo_id, path, repo_type=ref.repo_type, revision=revision or ref.revision or "main", token=token, endpoint=endpoint, local_dir=tmp)
            return Path(local).read_text(errors="ignore")
    if ref.source == "github":
        import requests
        headers = {"User-Agent": "modely-ai"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"https://raw.githubusercontent.com/{ref.repo_id}/{revision or ref.revision or 'main'}/{path}"
        r = requests.get(url, headers=headers, timeout=20)
        return r.text if r.status_code == 200 else ""
    return ""


def _is_inspectable_path(path: str) -> bool:
    name = path.lower().rsplit("/", 1)[-1]
    return name in {"requirements.txt", "setup.py", "pyproject.toml"} or name.startswith("readme") or name.endswith((".py", ".ipynb", ".sh", ".ps1", ".bat", ".md", ".txt"))


def _content_findings(text: str, path: str) -> list[ScanFinding]:
    findings = []
    for finding_id, pattern in _SUSPICIOUS_CODE_PATTERNS.items():
        if pattern.search(text):
            findings.append(ScanFinding(finding_id, "medium", "security", "Suspicious executable code pattern detected.", path=path, recommendation="Review code before importing or executing this asset."))
    for finding_id, pattern in _SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.append(ScanFinding(finding_id, "high", "security", "Possible secret material detected in text content.", path=path, recommendation="Remove secrets from published assets and rotate exposed credentials."))
    return findings


def _local_content_findings(path: str) -> list[ScanFinding]:
    root = Path(path).expanduser().resolve()
    candidates = [root] if root.is_file() else list(root.rglob("*")) if root.exists() else []
    findings = []
    for item in candidates:
        if not item.is_file():
            continue
        rel = item.name if root.is_file() else str(item.relative_to(root))
        findings.extend(_local_static_artifact_findings(item, rel))
        if item.suffix.lower() not in {".py", ".ipynb", ".sh", ".ps1", ".bat", ".md", ".txt", ".json", ".yaml", ".yml"} and item.name.lower() not in {"readme", ".env"}:
            continue
        try:
            if item.stat().st_size > _MAX_CODE_SCAN_BYTES:
                continue
            text = item.read_text(errors="ignore")
        except OSError:
            continue
        findings.extend(_content_findings(text, rel))
    return findings


def _local_static_artifact_findings(path: Path, rel: str) -> list[ScanFinding]:
    findings = []
    try:
        data = path.read_bytes()[:16]
    except OSError:
        return findings
    if rel.lower().endswith(".safetensors") and len(data) < 8:
        findings.append(ScanFinding("safetensors-header-invalid", "medium", "security", "Safetensors file is too small to contain a valid header.", path=rel, recommendation="Verify the safetensors artifact before use."))
    if rel.lower().endswith(_PICKLE_SUFFIXES) and data.startswith(b"\x80"):
        findings.append(ScanFinding("pickle-opcode", "high", "security", "Pickle protocol marker detected without deserializing.", path=rel, recommendation="Avoid loading pickle artifacts from untrusted sources."))
    return findings


def _dedupe_findings(findings: list[ScanFinding]) -> list[ScanFinding]:
    seen = set()
    output = []
    for finding in findings:
        key = (finding.id, finding.path)
        if key in seen:
            continue
        seen.add(key)
        output.append(finding)
    return sorted(output, key=lambda f: (-_SEVERITY_ORDER.get(f.severity, 0), f.category, f.id, f.path or ""))


__all__ = [name for name in globals() if not name.startswith("_")]
