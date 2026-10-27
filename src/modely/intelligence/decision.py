"""Evidence-driven source decision helpers."""

from __future__ import annotations

from typing import Optional

from ..mirror import verify_mirror
from ..policy import evaluate_scan_policy
from ..resolve import resolve_resource
from ..scan import scan_resource
from ..score import score_resource
from ..sources import rank_sources
from ..types import RepoRef
from ..uri import format_modely_uri

_RISK_PENALTY = {"none": 0, "low": 5, "medium": 20, "high": 40}


def decide_resource(
    query: str,
    *,
    source: str = "all",
    repo_type: str = "model",
    strategy: str = "balanced",
    limit: int = 5,
    threshold: float = 0.35,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    policy: Optional[dict] = None,
    probe: bool = False,
) -> dict:
    """Compose resolve, probe, score, scan, and policy evidence into a decision."""
    resolved = resolve_resource(query, source=source, repo_type=repo_type, limit=limit, threshold=threshold)
    warnings = list(resolved.warnings or [])
    probes = []
    probe_rank = {}
    if probe or strategy == "fastest":
        try:
            candidates = None if source == "all" else [source]
            probes = [p.to_dict() for p in rank_sources(query, candidates=candidates)]
            probe_rank = {p["source"]: i for i, p in enumerate(probes) if p.get("ok")}
        except Exception as exc:
            warnings.append(f"probe failed: {exc}")

    candidates = []
    for candidate in resolved.candidates:
        uri = candidate.modely_uri or _candidate_uri(candidate)
        item = {
            "uri": uri,
            "source": candidate.source,
            "repo_id": candidate.repo_id,
            "confidence": candidate.confidence,
            "signals": list(candidate.signals),
            "score": None,
            "risk_level": None,
            "policy": None,
            "rank_score": candidate.confidence * 100,
            "reasons": list(candidate.signals),
            "warnings": [],
            "evidence": {"resolve": (getattr(candidate, "metadata", {}) or {}).get("evidence", {})},
            "mirror": None,
        }
        try:
            scored = score_resource(uri, token=token, endpoint=endpoint)
            item["score"] = scored.score
            item["rank_score"] += scored.score
            item["reasons"].append(f"score={scored.score}")
        except Exception as exc:
            item["warnings"].append(f"score failed: {exc}")
        try:
            scanned = scan_resource(uri, token=token, endpoint=endpoint)
            item["risk_level"] = scanned.risk_level
            penalty = _RISK_PENALTY.get(scanned.risk_level, 0)
            item["rank_score"] -= penalty
            item["reasons"].append(f"risk={scanned.risk_level}")
            if policy:
                policy_result = evaluate_scan_policy(scanned, policy=policy)
                item["policy"] = policy_result
                if not policy_result["ok"]:
                    item["rank_score"] -= 100
                    item["reasons"].append("policy=failed")
        except Exception as exc:
            item["warnings"].append(f"scan failed: {exc}")
        if strategy == "safest":
            item["rank_score"] -= _RISK_PENALTY.get(item["risk_level"], 0)
        elif strategy == "fastest" and item["source"] in probe_rank:
            bonus = max(0, 50 - probe_rank[item["source"]] * 10)
            item["rank_score"] += bonus
            item["reasons"].append("fast-source")
            item["evidence"]["probe_rank_bonus"] = bonus
        elif strategy == "freshest":
            item["rank_score"] += 5 if candidate.result.get("last_modified") else 0
        candidates.append(item)

    _apply_mirror_evidence(candidates, token=token)
    candidates.sort(key=lambda c: c["rank_score"], reverse=True)
    return {
        "query": query,
        "strategy": strategy,
        "recommended": candidates[0] if candidates else None,
        "candidates": candidates,
        "resolve": resolved.to_dict(),
        "probes": probes,
        "warnings": warnings,
        "decision_evidence": {
            "strategy": strategy,
            "candidate_count": len(candidates),
            "policy_applied": bool(policy),
            "probe_applied": bool(probes),
            "mirror_applied": any(c.get("mirror") for c in candidates),
        },
    }


def _apply_mirror_evidence(candidates: list[dict], *, token=None) -> None:
    for item in candidates:
        mirror_target = _mirror_target(item.get("uri"), candidates)
        if not mirror_target:
            continue
        try:
            mirror = verify_mirror(item["uri"], mirror_target, token=token, deep=False)
            item["mirror"] = {"target": mirror_target, "status": mirror.get("status"), "confidence": mirror.get("confidence"), "reasons": mirror.get("reasons", [])}
            item["evidence"]["mirror"] = item["mirror"]
            if mirror.get("status") in {"ok", "likely"}:
                item["rank_score"] += 5
                item["reasons"].append(f"mirror={mirror.get('status')}")
            elif mirror.get("status") == "drifted":
                item["rank_score"] -= 30
                item["reasons"].append("mirror=drifted")
        except Exception as exc:
            item["warnings"].append(f"mirror failed: {exc}")


def _mirror_target(uri: str, candidates: list[dict]) -> Optional[str]:
    for item in candidates:
        other = item.get("uri")
        if other and other != uri:
            return other
    return None


def _candidate_uri(candidate) -> str:
    return format_modely_uri(RepoRef(candidate.source, candidate.repo_type, candidate.repo_id))
