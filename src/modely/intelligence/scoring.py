"""Asset scoring implementation."""

from __future__ import annotations

import json
from typing import List, Optional

from .analysis import analyze_resource
from ..cataloging.local_assets import analyze_local_path
from ..application.file_queries import format_file_size
from .scanning import find_scan_findings
from ..types import AssetAnalysis, AssetScore, ScoreBreakdown


def score_resource(
    resource: str,
    *,
    revision: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    profile: Optional[str] = None,
    deep: bool = True,
    source: str = "auto",
    repo_type: str = "auto",
    analyze_resource_func=None,
) -> AssetScore:
    """Score a resource's metadata, completeness, reproducibility, and safety."""
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
    return score_analysis(resource, analysis, revision=revision, deep=deep, profile=profile, include=include, exclude=exclude)


def score_analysis(resource: str, analysis: AssetAnalysis, *, revision=None, deep: bool = True, profile=None, include=None, exclude=None) -> AssetScore:
    """Score an existing asset analysis without fetching metadata again."""
    return _score_analysis(resource, analysis, revision=revision, deep=deep, profile=profile, include=include, exclude=exclude)


def _score_analysis(resource: str, analysis: AssetAnalysis, *, revision=None, deep: bool, profile, include, exclude) -> AssetScore:
    findings = find_scan_findings(analysis)
    breakdown = ScoreBreakdown(
        completeness=_score_completeness(analysis),
        metadata=_score_metadata(analysis),
        popularity=_score_popularity(analysis),
        freshness=_score_freshness(analysis, revision=revision),
        reproducibility=_score_reproducibility(analysis, revision=revision),
        safety=_score_safety(findings),
    )
    total = sum(breakdown.to_dict().values())
    score = max(0, min(100, int(total)))
    return AssetScore(
        resource=resource,
        score=score,
        grade=_grade(score),
        breakdown=breakdown,
        strengths=_strengths(analysis, breakdown),
        risks=[f"{f.id}: {f.message}" for f in findings],
        recommendations=_recommendations(findings, analysis),
        analysis=analysis,
        metadata={"deep": deep, "profile": profile, "include": include, "exclude": exclude},
    )


def score_path(path: str, *, deep: bool = True) -> AssetScore:
    """Score a local path without network access."""
    analysis = analyze_local_path(path, deep=deep)
    return _score_analysis(path, analysis, revision=None, deep=deep, profile=None, include=None, exclude=None)


def print_asset_score(result: AssetScore, *, as_json: bool = False) -> None:
    """Print an asset score."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Resource: {result.resource}")
    print(f"Score:    {result.score}/100 ({result.grade})")
    print("Breakdown:")
    for key, value in result.breakdown.to_dict().items():
        print(f"  - {key}: {value}")
    if result.analysis:
        print(f"Files:    {result.analysis.summary.selected_files} ({format_file_size(result.analysis.summary.selected_size)})")
    if result.strengths:
        print("Strengths:")
        for item in result.strengths:
            print(f"  - {item}")
    if result.risks:
        print("Risks:")
        for item in result.risks[:10]:
            print(f"  - {item}")
    if result.recommendations:
        print("Recommendations:")
        for item in result.recommendations[:10]:
            print(f"  - {item}")


def _score_completeness(analysis: AssetAnalysis) -> int:
    score = 0
    is_model = analysis.info.repo_type == "model"
    if analysis.has_card:
        score += 6
    if analysis.has_config:
        score += 6 if is_model else 3
    if analysis.has_tokenizer:
        score += 6 if is_model else 3
    elif not is_model:
        score += 3
    if analysis.summary.selected_files > 0:
        score += 6
    deep = (analysis.metadata or {}).get("deep") or {}
    formats = deep.get("formats") or {}
    if analysis.weight_formats or any(k in formats for k in ("parquet", "jsonl", "csv", "gguf", "safetensors", "onnx")):
        score += 6
    return min(score, 30)


def _score_metadata(analysis: AssetAnalysis) -> int:
    info = analysis.info
    score = 0
    if info.license:
        score += 8
    if info.description:
        score += 4
    if info.tags:
        score += 4
    if info.author or info.url:
        score += 4
    return min(score, 20)


def _score_popularity(analysis: AssetAnalysis) -> int:
    info = analysis.info
    downloads = info.downloads or 0
    likes = info.likes or 0
    score = 0
    if downloads >= 1_000_000:
        score += 8
    elif downloads >= 100_000:
        score += 6
    elif downloads >= 10_000:
        score += 4
    elif downloads > 0:
        score += 2
    if likes >= 1_000:
        score += 5
    elif likes >= 100:
        score += 3
    elif likes > 0:
        score += 1
    if info.forks:
        score += 2
    return min(score, 15)


def _score_freshness(analysis: AssetAnalysis, *, revision: Optional[str]) -> int:
    score = 0
    if analysis.info.last_modified:
        score += 6
    if analysis.info.created_at:
        score += 2
    if revision or analysis.info.revision:
        score += 2
    return min(score, 10)


def _score_reproducibility(analysis: AssetAnalysis, *, revision: Optional[str]) -> int:
    score = 0
    if any(f.sha256 for f in analysis.files):
        score += 5
    if revision or analysis.info.revision:
        score += 3
    if analysis.files and analysis.summary.selected_size > 0:
        score += 2
    return min(score, 10)


def _score_safety(findings) -> int:
    score = 15
    ids = {f.id for f in findings}
    if "missing-license" in ids:
        score -= 4
    for item in ("missing-card", "missing-config", "missing-tokenizer"):
        if item in ids:
            score -= 2
    if "large-weights" in ids:
        score -= 2
    if any(f.id in {"pickle-artifact", "unsafe-weight-format"} for f in findings):
        score -= 4
    if any(f.id == "remote-code" for f in findings):
        score -= 3
    return max(0, min(score, 15))


def _grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _strengths(analysis: AssetAnalysis, breakdown: ScoreBreakdown) -> list[str]:
    strengths = []
    if breakdown.completeness >= 24:
        strengths.append("asset appears complete")
    if analysis.info.license:
        strengths.append("license metadata present")
    if analysis.weight_formats.get("safetensors"):
        strengths.append("safetensors weights available")
    if any(f.sha256 for f in analysis.files):
        strengths.append("checksum metadata available")
    if (analysis.info.downloads or 0) or (analysis.info.likes or 0):
        strengths.append("popularity signals present")
    return strengths


def _recommendations(findings, analysis: AssetAnalysis) -> list[str]:
    recommendations = []
    for finding in findings:
        if finding.recommendation:
            recommendations.append(finding.recommendation)
    deep = (analysis.metadata or {}).get("deep") or {}
    recommendations.extend(deep.get("recommended_profiles") or [])
    return list(dict.fromkeys(recommendations))


__all__ = [name for name in globals() if not name.startswith("_")]
