"""Multi-resource comparison helpers."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from ..detail import get_resource_detail
from ..files import format_file_size


def compare_many_resources(resources: list[str], **kwargs) -> dict:
    """Compare several resources using the unified detail summary."""
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(resources)))) as executor:
        details = list(executor.map(lambda resource: get_resource_detail(resource, **kwargs), resources))
    items = []
    for resource, detail in zip(resources, details):
        info = detail.get("info") or {}
        summary = detail.get("summary") or {}
        score = detail.get("score") or {}
        scan = detail.get("scan") or {}
        items.append({
            "resource": resource,
            "source": info.get("source"),
            "repo_type": info.get("repo_type"),
            "repo_id": info.get("repo_id"),
            "license": info.get("license"),
            "selected_files": summary.get("selected_files", 0),
            "total_files": summary.get("total_files", 0),
            "selected_size": summary.get("selected_size", 0),
            "total_size": summary.get("total_size", 0),
            "score": score.get("score"),
            "grade": score.get("grade"),
            "risk_level": scan.get("risk_level"),
            "warnings": detail.get("warnings") or [],
        })
    return {"count": len(items), "resources": items, "summary": _comparison_summary(items)}


def print_many_comparison(result: dict, *, as_json: bool = False) -> None:
    """Print a compact multi-resource comparison."""
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    rows = [["Resource", "Source", "Type", "Files", "Size", "Score", "Risk", "License"]]
    for item in result.get("resources") or []:
        rows.append([
            item.get("repo_id") or item.get("resource") or "-",
            item.get("source") or "-",
            item.get("repo_type") or "-",
            f"{item.get('selected_files', 0)}/{item.get('total_files', 0)}",
            f"{format_file_size(item.get('selected_size', 0))}/{format_file_size(item.get('total_size', 0))}",
            f"{item.get('score', '-')}/{item.get('grade', '-')}",
            item.get("risk_level") or "-",
            item.get("license") or "-",
        ])
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        print("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
        if index == 0:
            print("  ".join("-" * width for width in widths))


def _comparison_summary(items: list[dict]) -> dict:
    return {
        "sources": sorted({item.get("source") for item in items if item.get("source")}),
        "repo_types": sorted({item.get("repo_type") for item in items if item.get("repo_type")}),
        "total_size": sum(item.get("total_size") or 0 for item in items),
        "max_risk_level": _max_risk(item.get("risk_level") for item in items),
    }


def _max_risk(levels) -> str:
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    best = "none"
    for level in levels:
        if order.get(level or "none", 0) > order.get(best, 0):
            best = level
    return best
