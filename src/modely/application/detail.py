"""Unified resource detail helpers."""

from __future__ import annotations

import json
from typing import Optional

from ..analyze import analyze_resource
from ..files import format_file_size
from ..scan import scan_analysis, scan_resource
from ..score import score_analysis, score_resource


def get_resource_detail(
    resource: str,
    *,
    revision: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    include=None,
    exclude=None,
    profile: Optional[str] = None,
    deep: bool = False,
    source: str = "auto",
    repo_type: str = "auto",
) -> dict:
    """Return a JSON-ready unified resource detail view."""
    analysis = analyze_resource(
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
    score = score_analysis(resource, analysis, revision=revision, deep=deep, profile=profile, include=include, exclude=exclude)
    scan = scan_analysis(resource, analysis, deep=deep, profile=profile, include=include, exclude=exclude)
    info = analysis.info
    return {
        "resource": resource,
        "info": info.to_dict(),
        "summary": analysis.summary.to_dict(),
        "card": analysis.card.to_dict() if analysis.card else None,
        "score": {"score": score.score, "grade": score.grade, "risks": score.risks, "recommendations": score.recommendations},
        "scan": {"risk_level": scan.risk_level, "summary": scan.summary, "findings": [f.to_dict() for f in scan.findings]},
        "files": {
            "largest": [f.to_dict() for f in analysis.largest_files],
            "categories": analysis.summary.categories,
            "weight_formats": analysis.weight_formats,
        },
        "warnings": analysis.warnings,
        "commands": {
            "info": _command("info", info.source, info.repo_type, info.repo_id),
            "files": _command("files", info.source, info.repo_type, info.repo_id),
            "get": _command("get", info.source, info.repo_type, info.repo_id),
            "plan": _command("plan", info.source, info.repo_type, info.repo_id),
        },
    }


def print_resource_detail(detail: dict, *, as_json: bool = False) -> None:
    """Print a unified resource detail view."""
    if as_json:
        print(json.dumps(detail, indent=2, ensure_ascii=False))
        return
    info = detail.get("info") or {}
    summary = detail.get("summary") or {}
    score = detail.get("score") or {}
    scan = detail.get("scan") or {}
    print(f"Source:        {info.get('source', '-')}")
    print(f"Repo type:     {info.get('repo_type', '-')}")
    print(f"Repo ID:       {info.get('repo_id', '-')}")
    if info.get("url"):
        print(f"URL:           {info.get('url')}")
    if info.get("license"):
        print(f"License:       {info.get('license')}")
    print(f"Files:         {summary.get('selected_files', 0)}/{summary.get('total_files', 0)}")
    print(f"Size:          {format_file_size(summary.get('selected_size', 0))} / {format_file_size(summary.get('total_size', 0))}")
    print(f"Score:         {score.get('score', '-')}/100 ({score.get('grade', '-')})")
    print(f"Risk:          {scan.get('risk_level', '-')}")
    if detail.get("warnings"):
        print("Warnings:")
        for warning in detail["warnings"]:
            print(f"  - {warning}")
    print("Commands:")
    for name, command in (detail.get("commands") or {}).items():
        print(f"  {name}: {command}")


def _command(command: str, source: str, repo_type: str, repo_id: str) -> str:
    return f"modely-ai {command} {repo_id} --source {source} --repo-type {repo_type}"
