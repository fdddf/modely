"""Search result grouping and lightweight comparison helpers."""

from __future__ import annotations

import json
import re
from typing import List

from .types import SearchResult


def normalize_repo_name(repo_id: str) -> str:
    """Normalize a repo id for conservative cross-source grouping."""
    name = repo_id.rsplit("/", 1)[-1].lower()
    name = re.sub(r"[_.\s]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


def dedupe_results(results: List[SearchResult]) -> list[dict]:
    """Group search results by normalized repository name."""
    groups = {}
    for result in results:
        key = normalize_repo_name(result.id)
        group = groups.setdefault(key, {"key": key, "sources": set(), "results": []})
        group["sources"].add(result.source)
        group["results"].append(result)
    output = []
    for group in groups.values():
        results_sorted = sorted(group["results"], key=lambda r: (r.downloads or 0, r.likes or 0), reverse=True)
        output.append({
            "key": group["key"],
            "sources": sorted(group["sources"]),
            "count": len(results_sorted),
            "results": results_sorted,
            "top": results_sorted[0] if results_sorted else None,
        })
    return sorted(output, key=lambda g: (len(g["sources"]), g["count"]), reverse=True)


def format_grouped_json(groups: list[dict]) -> str:
    """Format grouped search results as JSON."""
    def serialize(group):
        return {
            "key": group["key"],
            "sources": group["sources"],
            "count": group["count"],
            "top": group["top"].to_dict() if group.get("top") else None,
            "results": [r.to_dict() for r in group["results"]],
        }
    return json.dumps([serialize(g) for g in groups], indent=2, ensure_ascii=False)


def format_grouped_table(groups: list[dict], *, compare: bool = False) -> str:
    """Format grouped search results for terminal output."""
    if not groups:
        return "No results found."
    headers = ["Key", "Sources", "Types", "Count", "Top ID", "Downloads", "Likes"]
    rows = []
    for group in groups:
        top = group.get("top")
        rows.append([
            group["key"][:36],
            ",".join(group["sources"]),
            ",".join(sorted({r.repo_type for r in group["results"] if r.repo_type})),
            str(group["count"]),
            (top.id if top else "-")[:45],
            str(top.downloads if top else 0),
            str(top.likes if top else 0),
        ])
        if compare and len(group["results"]) > 1:
            for item in group["results"][:5]:
                rows.append(["  ↳", item.source, item.repo_type, "", item.id[:45], str(item.downloads or 0), str(item.likes or 0)])
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows)
    lines.append(f"\n{len(groups)} normalized group(s) shown.")
    return "\n".join(lines)
