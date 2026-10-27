"""Cross-source resource resolution helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from ..search import search
from ..search.dedupe import dedupe_results, normalize_repo_name
from ..search.types import SearchResult
from ..types import ResolveCandidate, ResolveResult
from ..uri import parse_modely_uri


def resolve_resource(
    query: str,
    *,
    source: str = "all",
    repo_type: str = "model",
    task: Optional[str] = None,
    library: Optional[str] = None,
    license: Optional[str] = None,
    limit: int = 10,
    threshold: float = 0.35,
    full: bool = False,
) -> ResolveResult:
    """Resolve a query to likely equivalent resources across sources."""
    search_query = _query_from_resource(query)
    results = search(
        search_query,
        source=source,
        repo_type=repo_type,
        task=task,
        library=library,
        license=license,
        limit=limit,
        full=full,
    )
    groups = dedupe_results(results)
    group_by_key = {group["key"]: group for group in groups}

    candidates = []
    for result in results:
        group = group_by_key.get(normalize_repo_name(result.id), {"sources": [result.source], "results": [result]})
        confidence, signals = score_candidate(search_query, result, group)
        if confidence < threshold:
            continue
        evidence = _candidate_evidence(search_query, result, group, confidence, signals)
        candidates.append(
            ResolveCandidate(
                result=result.to_dict(),
                source=result.source,
                repo_type=result.repo_type,
                repo_id=result.id,
                modely_uri=result.modely_uri,
                confidence=confidence,
                signals=signals,
                metadata={"evidence": evidence},
            )
        )

    candidates.sort(key=lambda c: (c.confidence, _popularity(c.result), c.repo_id), reverse=True)
    group_payloads = _build_group_payloads(groups, search_query, threshold)
    canonical = _canonical_name(candidates, group_payloads)
    warnings = []
    if not candidates:
        warnings.append("no-candidates-above-threshold")
    elif len({c.source for c in candidates}) < 2:
        warnings.append("single-source-only")

    return ResolveResult(
        query=query,
        canonical=canonical,
        repo_type=repo_type,
        candidates=candidates,
        groups=group_payloads,
        warnings=warnings,
        metadata={
            "search_query": search_query,
            "source": source,
            "threshold": threshold,
            "limit": limit,
            "total_results": len(results),
        },
    )


def normalize_resolve_text(value: Any) -> str:
    """Normalize free text for conservative resolve scoring."""
    if isinstance(value, dict):
        value = value.get("Name") or value.get("name") or value.get("login") or value.get("id") or ""
    elif isinstance(value, (list, tuple, set)):
        value = next((item for item in value if item), "")
    text = str(value or "").rsplit("/", 1)[-1].lower()
    text = re.sub(r"[_.\s]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def score_candidate(query: str, result: SearchResult, group: dict) -> tuple[float, list[str]]:
    """Return a deterministic confidence score and matching signals."""
    score = 0.0
    signals = []
    query_norm = normalize_resolve_text(query)
    name_norm = normalize_resolve_text(result.name or result.id)
    id_norm = normalize_resolve_text(result.id)

    if query_norm and query_norm in {name_norm, id_norm}:
        score += 0.45
        signals.append("name-exact")
    elif query_norm and (query_norm in name_norm or name_norm in query_norm or query_norm in id_norm or id_norm in query_norm):
        score += 0.25
        signals.append("name-partial")

    group_results = group.get("results", [])
    group_sources = set(group.get("sources", []))
    if len(group_sources) > 1:
        score += 0.20
        signals.append("cross-source-group")

    authors = {normalize_resolve_text(r.author or "") for r in group_results if getattr(r, "author", None)}
    author_norm = normalize_resolve_text(result.author or "")
    if author_norm and (author_norm in query_norm or len(authors) < len(group_results)):
        score += 0.10
        signals.append("author-match")

    task_values = {r.pipeline_tag for r in group_results if getattr(r, "pipeline_tag", None)}
    if result.pipeline_tag and len(task_values) == 1 and len(group_results) > 1:
        score += 0.10
        signals.append("task-match")

    licenses = {r.license for r in group_results if getattr(r, "license", None)}
    if result.license and len(licenses) == 1 and len(group_results) > 1:
        score += 0.05
        signals.append("license-match")

    if (result.downloads or 0) or (result.likes or 0) or (result.stars or 0) or (result.forks or 0):
        score += 0.05
        signals.append("popularity")

    return round(min(score, 1.0), 3), signals


def _candidate_evidence(query: str, result: SearchResult, group: dict, confidence: float, signals: list[str]) -> dict:
    group_results = group.get("results", [])
    sources = sorted(set(group.get("sources", [])))
    return {
        "query_normalized": normalize_resolve_text(query),
        "name_normalized": normalize_resolve_text(result.name or result.id),
        "id_normalized": normalize_resolve_text(result.id),
        "confidence": confidence,
        "signals": signals,
        "group_sources": sources,
        "group_size": len(group_results),
        "author": result.author,
        "task": result.pipeline_tag,
        "license": result.license,
        "popularity": _popularity(result.to_dict()),
    }


def format_resolve_json(result: ResolveResult) -> str:
    """Format a resolve result as JSON."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


def print_resolve_result(result: ResolveResult, *, as_json: bool = False) -> None:
    """Print a resolve result."""
    if as_json:
        print(format_resolve_json(result))
        return
    print(format_resolve_table(result))


def format_resolve_table(result: ResolveResult) -> str:
    """Format a resolve result for terminal output."""
    if not result.candidates:
        return "No resolve candidates found."

    headers = ["Confidence", "Source", "Repo ID", "URI", "Signals"]
    rows = []
    for candidate in result.candidates:
        rows.append([
            f"{candidate.confidence:.3f}",
            candidate.source,
            candidate.repo_id[:44],
            (candidate.modely_uri or "-")[:48],
            ",".join(candidate.signals)[:40],
        ])
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    lines = [
        f"Canonical: {result.canonical or '-'}",
        f"Query:     {result.query}",
        "",
        "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)),
        "  ".join("-" * w for w in widths),
    ]
    lines.extend("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows)
    lines.append("")
    lines.append(f"{len(result.candidates)} candidate(s) across {len({c.source for c in result.candidates})} source(s).")
    if result.warnings:
        lines.append("Warnings: " + ", ".join(result.warnings))
    return "\n".join(lines)


def _query_from_resource(query: str) -> str:
    if "://" not in query:
        return query
    try:
        ref = parse_modely_uri(query)
        return ref.repo_id.rsplit("/", 1)[-1]
    except Exception:
        return query.rsplit("/", 1)[-1]


def _build_group_payloads(groups: list[dict], query: str, threshold: float) -> list[dict]:
    payloads = []
    for group in groups:
        scored = [score_candidate(query, result, group)[0] for result in group.get("results", [])]
        best_confidence = max(scored) if scored else 0.0
        if best_confidence < threshold:
            continue
        top = group.get("top")
        payloads.append({
            "key": group["key"],
            "sources": group["sources"],
            "count": group["count"],
            "confidence": best_confidence,
            "top": top.to_dict() if top else None,
        })
    return sorted(payloads, key=lambda g: (g["confidence"], len(g["sources"]), g["count"]), reverse=True)


def _canonical_name(candidates: list[ResolveCandidate], groups: list[dict]) -> Optional[str]:
    if candidates:
        return candidates[0].repo_id.rsplit("/", 1)[-1]
    if groups:
        return groups[0]["key"]
    return None


def _popularity(result: dict) -> int:
    return int(result.get("downloads") or 0) + int(result.get("likes") or 0) + int(result.get("stars") or 0) + int(result.get("forks") or 0)
