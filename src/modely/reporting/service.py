"""Resource report service implementation."""

from __future__ import annotations

import html
import json
import os
from collections.abc import Callable
from typing import Any

from ..doctor import doctor_resource as default_doctor_resource
from ..scan import scan_path as default_scan_path
from ..score import score_path as default_score_path


def create_resource_report(
    resource: str,
    *,
    format: str = "markdown",
    doctor_func: Callable[..., dict[str, Any]] = default_doctor_resource,
    scan_path_func: Callable[..., Any] = default_scan_path,
    score_path_func: Callable[..., Any] = default_score_path,
    **kwargs,
) -> str:
    """Create a simple resource report from doctor signals."""
    report = (
        _local_report(resource, scan_path_func=scan_path_func, score_path_func=score_path_func)
        if os.path.exists(resource) and "://" not in resource
        else doctor_func(resource, **kwargs)
    )
    if format == "json":
        return json.dumps(report, indent=2, ensure_ascii=False)
    if format == "html":
        return _html_report(report)
    if format == "markdown":
        return _markdown_report(report)
    raise ValueError(f"Unsupported report format: {format}")


def _local_report(path: str, *, scan_path_func=default_scan_path, score_path_func=default_score_path) -> dict:
    score = score_path_func(path).to_dict()
    scan = scan_path_func(path).to_dict()
    return {
        "query": path,
        "recommended": path,
        "strategy": "local",
        "resolve": None,
        "score": score,
        "scan": scan,
        "probes": [],
        "warnings": [],
        "next_steps": [],
    }


def _markdown_report(report: dict) -> str:
    lines = [f"# modely report: {report['query']}", ""]
    lines.append(f"- Recommended: `{report.get('recommended') or '-'}`")
    score = report.get("score") or {}
    if score:
        lines.append(f"- Score: {score.get('score')}/100 ({score.get('grade')})")
    scan = report.get("scan") or {}
    if scan:
        lines.append(f"- Risk: {scan.get('risk_level')}")
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {w}" for w in report["warnings"])
    return "\n".join(lines) + "\n"


def _html_report(report: dict) -> str:
    title = html.escape(f"modely report: {report['query']}")
    recommended = html.escape(str(report.get("recommended") or "-"))
    score = report.get("score") or {}
    scan = report.get("scan") or {}
    warning_items = "".join(f"<li>{html.escape(str(w))}</li>" for w in report.get("warnings") or [])
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p><strong>Recommended:</strong> <code>{recommended}</code></p>"
        f"<p><strong>Score:</strong> {html.escape(str(score.get('score', '-')))} / 100 ({html.escape(str(score.get('grade', '-')))} )</p>"
        f"<p><strong>Risk:</strong> {html.escape(str(scan.get('risk_level', '-')))}</p>"
        f"<h2>Warnings</h2><ul>{warning_items}</ul>"
        "</body></html>\n"
    )


__all__ = ["create_resource_report"]
