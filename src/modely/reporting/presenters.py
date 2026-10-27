"""Presentation boundary for CLI output.

The first phase wraps existing print helpers to preserve output compatibility.
"""

from __future__ import annotations

import json

from ..files import print_file_list, print_file_tree
from ..info import print_repo_info
from ..plan import print_download_plan


def present_repo_info(info, *, as_json: bool = False) -> None:
    print_repo_info(info, as_json=as_json)


def present_file_list(files, source: str, repo_id: str, *, as_json: bool = False, summary: bool = False) -> None:
    print_file_list(files, source, repo_id, as_json=as_json, summary=summary)


def present_file_tree(files, *, as_json: bool = False) -> None:
    print_file_tree(files, as_json=as_json)


def present_download_plan(plan, *, as_json: bool = False) -> None:
    print_download_plan(plan, as_json=as_json)


def _report_dict(report):
    return report.to_dict() if hasattr(report, "to_dict") else report


def _print_sync_report(report, *, title: str, as_json: bool = False) -> None:
    payload = _report_dict(report)
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(title)
    summary = payload.get("summary") or {}
    if summary:
        print("Summary: " + ", ".join(f"{key}={value}" for key, value in summary.items()))
    targets = payload.get("targets") or []
    states = payload.get("states") or {}
    if targets:
        print("Targets:")
        for target in targets:
            state = states.get(target.get("id"), {}) or {}
            labels = ",".join(target.get("labels") or []) or "-"
            print(f"  - {target.get('id')} [{state.get('status', 'unknown')}] {target.get('resource')}")
            print(f"    Local: {target.get('local_dir')}  Revision: {target.get('revision') or '-'}  Labels: {labels}")
    elif not payload.get("runs"):
        print("No sync-center targets found.")
    runs = payload.get("runs") or []
    if runs:
        print("Runs:")
        for run in runs:
            print(f"  - {run.get('id')} {run.get('action')} {run.get('status')} target={run.get('target_id')}")
            if run.get("path"):
                print(f"    Path: {run.get('path')}")
            if run.get("error"):
                print(f"    Error: {run.get('error')}")
            for warning in run.get("warnings") or []:
                print(f"    Warning: {warning}")
    for warning in payload.get("warnings") or []:
        print(f"Warning: {warning}")


def present_sync_targets(report, *, as_json: bool = False) -> None:
    _print_sync_report(report, title="Sync center targets", as_json=as_json)


def present_sync_runs(report, *, as_json: bool = False) -> None:
    _print_sync_report(report, title="Sync center runs", as_json=as_json)


def present_sync_plan(report, *, as_json: bool = False) -> None:
    _print_sync_report(report, title="Sync center plan", as_json=as_json)


def present_sync_check(report, *, as_json: bool = False) -> None:
    _print_sync_report(report, title="Sync center drift check", as_json=as_json)


def present_sync_catalog(report, *, as_json: bool = False) -> None:
    _print_sync_report(report, title="Sync center catalog", as_json=as_json)
