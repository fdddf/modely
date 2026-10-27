"""Markdown report formatter integration point.

Supports generic report dicts and GovernanceReport DTOs with
permission-filtered, redaction-aware rendering.  Stable field names
are preserved across all rendering backends.
"""

from __future__ import annotations

from typing import Any

from ..governance.redaction import permission_filter_items


def format_markdown(report: dict) -> str:
    """Format a generic report dictionary as compact markdown."""
    title = report.get("query") or report.get("resource") or "modely report"
    lines = [f"# modely report: {title}", ""]
    if "recommended" in report:
        lines.append(f"- Recommended: `{report.get('recommended') or '-'}`")
    if report.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"


def format_governance_report_markdown(
    report: Any,
    *,
    allowed_actions: set[str] | None = None,
    principal_scope: str | None = None,
) -> str:
    """Format a GovernanceReport DTO as permission-filtered, redacted markdown.

    Stable field names: title, summary, assets, policy_decisions, approvals,
    audit_events, metadata.
    """
    d = report.to_dict() if hasattr(report, "to_dict") else dict(report)

    title = d.get("title", "Governance Report")
    lines = [f"# {title}", ""]

    # ── Summary ──
    summary = d.get("summary") or {}
    if summary:
        lines.append("## Summary")
        for k, v in summary.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    # ── Assets ──
    raw_assets = d.get("assets") or []
    assets = permission_filter_items(raw_assets, allowed_actions=allowed_actions, principal_scope=principal_scope)
    if assets:
        lines.append(f"## Assets ({len(assets)})")
        for asset in assets:
            if isinstance(asset, dict):
                aid = asset.get("id") or asset.get("repo_id") or "-"
                src = asset.get("source") or "-"
                lic = asset.get("license") or "-"
                vis = asset.get("visibility") or "-"
                lines.append(f"- `{aid}` | source: {src} | license: {lic} | visibility: {vis}")
        lines.append("")

    # ── Policy Decisions ──
    raw_decisions = d.get("policy_decisions") or []
    decisions = permission_filter_items(raw_decisions, allowed_actions=allowed_actions, principal_scope=principal_scope)
    if decisions:
        lines.append(f"## Policy Decisions ({len(decisions)})")
        for dec in decisions:
            if isinstance(dec, dict):
                outcome = dec.get("outcome", "-")
                reasons = ", ".join(dec.get("reasons", []) or [])
                risk = dec.get("risk_level", "-")
                lines.append(f"- **{outcome}** (risk: {risk}) — {reasons or 'no reasons given'}")
        lines.append("")

    # ── Approvals ──
    raw_approvals = d.get("approvals") or []
    approvals = permission_filter_items(raw_approvals, allowed_actions=allowed_actions, principal_scope=principal_scope)
    if approvals:
        lines.append(f"## Approvals ({len(approvals)})")
        for app in approvals:
            if isinstance(app, dict):
                state = app.get("state") or app.get("status") or "-"
                asset = app.get("asset_id") or "-"
                lines.append(f"- `{asset}` → {state}")
        lines.append("")

    # ── Audit Events ──
    raw_audit = d.get("audit_events") or []
    audit_events = permission_filter_items(raw_audit, allowed_actions=allowed_actions, principal_scope=principal_scope)
    if audit_events:
        lines.append(f"## Audit Events ({len(audit_events)})")
        for evt in audit_events:
            if isinstance(evt, dict):
                evt_action = evt.get("action") or evt.get("event_type") or "-"
                timestamp = evt.get("timestamp") or evt.get("created_at") or "-"
                lines.append(f"- `{evt_action}` at {timestamp}")
        lines.append("")

    # ── Metadata ──
    meta = d.get("metadata") or {}
    if meta:
        lines.append("## Metadata")
        for k, v in meta.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    return "\n".join(lines) + "\n"


__all__ = ["format_governance_report_markdown", "format_markdown"]
