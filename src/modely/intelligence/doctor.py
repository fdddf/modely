"""Aggregate resource diagnosis helpers."""

from __future__ import annotations

import json
from typing import Optional

from .decision import decide_resource
from ..resolve import resolve_resource
from ..scan import scan_resource
from ..score import score_resource
from ..sources import rank_sources
from ..types import RepoRef
from ..uri import format_modely_uri


def doctor_resource(
    query: str,
    *,
    source: str = "all",
    repo_type: str = "model",
    strategy: str = "balanced",
    probe: bool = False,
    limit: int = 5,
    threshold: float = 0.35,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    policy: Optional[dict] = None,
) -> dict:
    """Diagnose a resource or query and recommend the next action."""
    warnings = []
    resolve = None
    recommended = query if "://" in query else None

    if recommended is None:
        resolve = resolve_resource(query, source=source, repo_type=repo_type, limit=limit, threshold=threshold)
        if resolve.candidates:
            candidate = resolve.candidates[0]
            recommended = candidate.modely_uri or _candidate_uri(candidate)
        else:
            warnings.extend(resolve.warnings or ["no-candidates"])

    score = None
    scan = None
    if recommended:
        try:
            score = score_resource(recommended, token=token, endpoint=endpoint).to_dict()
        except Exception as exc:
            warnings.append(f"score failed: {exc}")
        try:
            scan = scan_resource(recommended, token=token, endpoint=endpoint).to_dict()
        except Exception as exc:
            warnings.append(f"scan failed: {exc}")

    probes = []
    if probe:
        try:
            candidates = None if source == "all" else [source]
            probes = [p.to_dict() for p in rank_sources(recommended or query, candidates=candidates)]
        except Exception as exc:
            warnings.append(f"probe failed: {exc}")

    decision = None
    if recommended:
        try:
            decision = decide_resource(query, source=source, repo_type=repo_type, strategy=strategy,
                                       limit=limit, threshold=threshold, token=token,
                                       endpoint=endpoint, policy=policy, probe=probe)
        except Exception as exc:
            warnings.append(f"decision failed: {exc}")

    return {
        "query": query,
        "recommended": recommended,
        "strategy": strategy,
        "resolve": resolve.to_dict() if resolve else None,
        "score": score,
        "scan": scan,
        "probes": probes,
        "decision": decision,
        "warnings": warnings,
        "next_steps": [f"modely get {recommended}"] if recommended else [],
    }


def _candidate_uri(candidate) -> str:
    return format_modely_uri(RepoRef(candidate.source, candidate.repo_type, candidate.repo_id))


def print_doctor_report(report: dict, *, as_json: bool = False) -> None:
    """Print a doctor report."""
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print(f"Query:       {report['query']}")
    print(f"Recommended: {report.get('recommended') or '-'}")
    score = report.get("score") or {}
    if score:
        print(f"Score:       {score.get('score')}/100 ({score.get('grade')})")
    scan = report.get("scan") or {}
    if scan:
        print(f"Risk:        {scan.get('risk_level')}")
    if report.get("next_steps"):
        print("Next steps:")
        for step in report["next_steps"]:
            print(f"  - {step}")
    if report.get("warnings"):
        print("Warnings:")
        for warning in report["warnings"]:
            print(f"  - {warning}")
