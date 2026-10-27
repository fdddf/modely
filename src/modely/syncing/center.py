"""Local resource sync-center store and orchestration helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..cataloging.catalog import catalog_summary
from ..common import cache
from ..types import CatalogEntry, CatalogReport, ResourceSyncRun, ResourceSyncState, ResourceSyncTarget
from ..uri import parse_modely_uri

SYNC_CENTER_DIRNAME = "sync-center"
SUPPORTED_DRIFT_SOURCES = {"hf", "ms"}
SUPPORTED_DRIFT_REPO_TYPES = {"model", "dataset"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_sync_center_dir() -> Path:
    """Return the default local sync-center directory."""
    return Path(cache.CONFIG_DIR) / SYNC_CENTER_DIRNAME


def _sync_center_dir(config_dir: Optional[str | Path] = None) -> Path:
    return Path(config_dir).expanduser() if config_dir else default_sync_center_dir()


def _targets_path(config_dir: Optional[str | Path] = None) -> Path:
    return _sync_center_dir(config_dir) / "targets.json"


def _states_path(config_dir: Optional[str | Path] = None) -> Path:
    return _sync_center_dir(config_dir) / "state.json"


def _runs_path(config_dir: Optional[str | Path] = None) -> Path:
    return _sync_center_dir(config_dir) / "runs.jsonl"


def _catalog_dir(config_dir: Optional[str | Path] = None) -> Path:
    return _sync_center_dir(config_dir) / "catalog"


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r") as f:
        return json.load(f)


def _coerce_list(value: Any) -> list:
    return list(value or [])


def _coerce_dict(value: Any) -> dict:
    return dict(value or {})


def _target_from_dict(data: dict) -> ResourceSyncTarget:
    allowed = {field.name for field in fields(ResourceSyncTarget)}
    payload = {key: value for key, value in data.items() if key in allowed}
    payload["include"] = _coerce_list(payload.get("include")) or None
    payload["exclude"] = _coerce_list(payload.get("exclude")) or None
    payload["labels"] = _coerce_list(payload.get("labels"))
    payload["metadata"] = _coerce_dict(payload.get("metadata"))
    return ResourceSyncTarget(**payload)


def _state_from_dict(data: dict) -> ResourceSyncState:
    allowed = {field.name for field in fields(ResourceSyncState)}
    payload = {key: value for key, value in data.items() if key in allowed}
    payload["metadata"] = _coerce_dict(payload.get("metadata"))
    return ResourceSyncState(**payload)


def _run_from_dict(data: dict) -> ResourceSyncRun:
    allowed = {field.name for field in fields(ResourceSyncRun)}
    payload = {key: value for key, value in data.items() if key in allowed}
    payload["warnings"] = _coerce_list(payload.get("warnings"))
    payload["metadata"] = _coerce_dict(payload.get("metadata"))
    return ResourceSyncRun(**payload)


def make_target_id(resource: str, *, local_dir: Optional[str] = None, revision: Optional[str] = None) -> str:
    raw = "|".join([resource, local_dir or "", revision or ""])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", resource.replace("://", "-"))
    slug = slug.strip("-._")[:40] or "target"
    return f"{slug}-{digest}"


def load_targets(config_dir: Optional[str | Path] = None) -> list[ResourceSyncTarget]:
    return [_target_from_dict(item) for item in _read_json(_targets_path(config_dir), [])]


def save_targets(targets: list[ResourceSyncTarget], config_dir: Optional[str | Path] = None) -> None:
    _write_json_atomic(_targets_path(config_dir), [target.to_dict() for target in targets])


def load_states(config_dir: Optional[str | Path] = None) -> dict[str, ResourceSyncState]:
    data = _read_json(_states_path(config_dir), {})
    return {key: _state_from_dict(value) for key, value in data.items()}


def save_states(states: dict[str, ResourceSyncState], config_dir: Optional[str | Path] = None) -> None:
    _write_json_atomic(_states_path(config_dir), {key: value.to_dict() for key, value in states.items()})


def append_run(run: ResourceSyncRun, config_dir: Optional[str | Path] = None) -> None:
    path = _runs_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(run.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def list_runs(*, target_id: Optional[str] = None, limit: int = 50, config_dir: Optional[str | Path] = None) -> list[ResourceSyncRun]:
    path = _runs_path(config_dir)
    if not path.exists():
        return []
    runs = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                run = _run_from_dict(json.loads(line))
                if target_id is None or run.target_id == target_id:
                    runs.append(run)
    runs.reverse()
    return runs[:limit]


def _parse_resource_defaults(resource: str, source: str = "auto", repo_type: str = "auto", revision: Optional[str] = None) -> dict:
    if "://" not in resource:
        return {"source": source, "repo_type": repo_type, "revision": revision}
    try:
        ref = parse_modely_uri(resource)
    except Exception:
        return {"source": source, "repo_type": repo_type, "revision": revision}
    return {
        "source": source if source != "auto" else ref.source,
        "repo_type": repo_type if repo_type != "auto" else ref.repo_type,
        "revision": revision if revision is not None else ref.revision,
    }


def add_target(
    resource: str,
    *,
    id: Optional[str] = None,
    local_dir: str,
    source: str = "auto",
    repo_type: str = "auto",
    revision: Optional[str] = None,
    include=None,
    exclude=None,
    profile: Optional[str] = None,
    prefer: str = "default",
    cache_dir: Optional[str] = None,
    token_env: Optional[str] = None,
    checksum: bool = False,
    force_download: bool = False,
    manifest: Optional[str] = None,
    report: Optional[str] = None,
    labels=None,
    config_dir: Optional[str | Path] = None,
    record_audit_event_func=None,
    default_sync_center_dir_func=None,
) -> ResourceSyncTarget:
    if config_dir is None and default_sync_center_dir_func is not None:
        config_dir = default_sync_center_dir_func()
    defaults = _parse_resource_defaults(resource, source, repo_type, revision)
    target_id = id or make_target_id(resource, local_dir=local_dir, revision=defaults["revision"])
    targets = load_targets(config_dir)
    if any(target.id == target_id for target in targets):
        raise ValueError(f"Sync target already exists: {target_id}")
    target = ResourceSyncTarget(
        id=target_id,
        resource=resource,
        local_dir=local_dir,
        source=defaults["source"],
        repo_type=defaults["repo_type"],
        revision=defaults["revision"],
        include=_coerce_list(include) or None,
        exclude=_coerce_list(exclude) or None,
        profile=profile,
        prefer=prefer,
        token_env=token_env,
        cache_dir=cache_dir,
        checksum=checksum,
        force_download=force_download,
        manifest=manifest,
        report=report,
        labels=_coerce_list(labels),
        metadata={"created_at": _now_iso()},
    )
    targets.append(target)
    save_targets(targets, config_dir)
    states = load_states(config_dir)
    states[target.id] = ResourceSyncState(target.id, "registered", metadata={"created_at": target.metadata["created_at"]})
    save_states(states, config_dir)
    run = ResourceSyncRun(uuid.uuid4().hex, target.id, "add", "ok", _now_iso(), finished_at=_now_iso(), resource=target.resource, local_dir=target.local_dir)
    append_run(run, config_dir)
    if record_audit_event_func:
        record_audit_event_func("sync-center.add", resource=target.resource, metadata={"target_id": target.id, "local_dir": target.local_dir})
    return target


def list_targets(config_dir: Optional[str | Path] = None) -> list[ResourceSyncTarget]:
    return load_targets(config_dir)


def get_target(target_id: str, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    for target in load_targets(config_dir):
        if target.id == target_id:
            return target
    raise ValueError(f"Sync target not found: {target_id}")


def remove_target(target_id: str, *, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    targets = load_targets(config_dir)
    kept = [target for target in targets if target.id != target_id]
    removed = [target for target in targets if target.id == target_id]
    if not removed:
        raise ValueError(f"Sync target not found: {target_id}")
    save_targets(kept, config_dir)
    states = load_states(config_dir)
    states.pop(target_id, None)
    save_states(states, config_dir)
    return removed[0]


def set_target_enabled(target_id: str, enabled: bool, *, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    targets = load_targets(config_dir)
    for index, target in enumerate(targets):
        if target.id == target_id:
            target.enabled = enabled
            targets[index] = target
            save_targets(targets, config_dir)
            states = load_states(config_dir)
            state = states.get(target.id, ResourceSyncState(target.id, "registered"))
            state.status = "enabled" if enabled else "disabled"
            states[target.id] = state
            save_states(states, config_dir)
            return target
    raise ValueError(f"Sync target not found: {target_id}")


def enable_target(target_id: str, *, enabled: bool = True, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    return set_target_enabled(target_id, enabled, config_dir=config_dir)


def _merged_runtime_token(target: ResourceSyncTarget, token: Optional[str]) -> Optional[str]:
    if token:
        return token
    if target.token_env:
        return os.environ.get(target.token_env)
    return None


def _error_run(target: ResourceSyncTarget, action: str, exc: Exception) -> ResourceSyncRun:
    now = _now_iso()
    return ResourceSyncRun(uuid.uuid4().hex, target.id, action, "error", now, finished_at=now, resource=target.resource, local_dir=target.local_dir, error=str(exc))


def _plan_summary(plan: Any) -> dict:
    summary = getattr(plan, "summary", None)
    return summary.to_dict() if hasattr(summary, "to_dict") else dict(summary or {})


def plan_target(target: ResourceSyncTarget, *, token: Optional[str] = None, config_dir: Optional[str | Path] = None, create_download_plan_func=None) -> tuple[ResourceSyncRun, Any]:
    now = _now_iso()
    try:
        plan = create_download_plan_func(
            target.resource,
            source=target.source,
            repo_type=target.repo_type,
            revision=target.revision,
            include=target.include,
            exclude=target.exclude,
            profile=target.profile,
            prefer=target.prefer,
            cache_dir=target.cache_dir,
            local_dir=target.local_dir,
            token=_merged_runtime_token(target, token),
        )
        run = ResourceSyncRun(uuid.uuid4().hex, target.id, "plan", "ok", now, finished_at=_now_iso(), resource=target.resource, local_dir=target.local_dir, metadata=_plan_summary(plan))
        states = load_states(config_dir)
        state = states.get(target.id, ResourceSyncState(target.id, "registered"))
        state.status = "planned"
        state.last_planned_at = run.finished_at
        states[target.id] = state
        save_states(states, config_dir)
        append_run(run, config_dir)
        return run, plan
    except Exception as exc:
        run = _error_run(target, "plan", exc)
        append_run(run, config_dir)
        return run, None


def _sync_summary(path: str) -> dict:
    return {"path": path}


def sync_target(target: ResourceSyncTarget, *, token: Optional[str] = None, force_download: Optional[bool] = None,
                checksum: Optional[bool] = None, config_dir: Optional[str | Path] = None, sync_resource_func=None) -> ResourceSyncRun:
    now = _now_iso()
    try:
        path = sync_resource_func(
            target.resource,
            local_dir=target.local_dir,
            revision=target.revision,
            include=target.include,
            exclude=target.exclude,
            token=_merged_runtime_token(target, token),
            cache_dir=target.cache_dir,
            manifest=target.manifest,
            checksum=target.checksum if checksum is None else checksum,
            force_download=target.force_download if force_download is None else force_download,
            source=target.source,
            prefer=target.prefer,
            profile=target.profile,
            report=target.report,
        )
        run = ResourceSyncRun(uuid.uuid4().hex, target.id, "sync", "ok", now, finished_at=_now_iso(), resource=target.resource, local_dir=target.local_dir, path=path, manifest_path=target.manifest, report_path=target.report, metadata=_sync_summary(path))
        states = load_states(config_dir)
        state = states.get(target.id, ResourceSyncState(target.id, "registered"))
        state.status = "synced"
        state.last_synced_at = run.finished_at
        state.last_download_path = path
        state.last_manifest_path = target.manifest
        state.last_report_path = target.report
        state.run_count += 1
        states[target.id] = state
        save_states(states, config_dir)
        append_run(run, config_dir)
        return run
    except Exception as exc:
        run = _error_run(target, "sync", exc)
        append_run(run, config_dir)
        return run


def check_target_drift(target: ResourceSyncTarget, *, config_dir: Optional[str | Path] = None, get_remote_fingerprint_func=None) -> ResourceSyncRun:
    now = _now_iso()
    if target.source not in SUPPORTED_DRIFT_SOURCES or target.repo_type not in SUPPORTED_DRIFT_REPO_TYPES:
        run = ResourceSyncRun(uuid.uuid4().hex, target.id, "check", "unsupported", now, finished_at=_now_iso(), resource=target.resource, local_dir=target.local_dir, warnings=["remote drift checks are supported for hf/ms model and dataset targets"])
        states = load_states(config_dir)
        state = states.get(target.id, ResourceSyncState(target.id, "registered"))
        state.status = "unsupported"
        state.last_checked_at = run.finished_at
        states[target.id] = state
        save_states(states, config_dir)
        append_run(run, config_dir)
        return run
    try:
        states = load_states(config_dir)
        state = states.get(target.id, ResourceSyncState(target.id, "registered"))
        before = state.last_fingerprint
        after = get_remote_fingerprint_func(target)
        status = "unchanged" if before in {None, after} else "drifted"
        state.status = status
        state.last_checked_at = _now_iso()
        state.last_fingerprint = after
        states[target.id] = state
        save_states(states, config_dir)
        run = ResourceSyncRun(uuid.uuid4().hex, target.id, "check", status, now, finished_at=state.last_checked_at, resource=target.resource, local_dir=target.local_dir, fingerprint_before=before, fingerprint_after=after)
        append_run(run, config_dir)
        return run
    except Exception as exc:
        run = _error_run(target, "check", exc)
        append_run(run, config_dir)
        return run


def _catalog_entry_with_target(entry: CatalogEntry, target: ResourceSyncTarget) -> CatalogEntry:
    metadata = dict(entry.metadata or {})
    metadata["sync_target_id"] = target.id
    entry.metadata = metadata
    return entry


def _combine_catalog_reports(items: list[tuple[ResourceSyncTarget, CatalogReport]]) -> CatalogReport:
    entries = []
    warnings = []
    for target, report in items:
        entries.extend(_catalog_entry_with_target(entry, target) for entry in report.entries)
        warnings.extend(report.warnings)
    summary = catalog_summary(entries)
    summary["targets"] = len(items)
    return CatalogReport(root="sync-center", entries=entries, summary=summary, warnings=warnings, metadata={"mode": "sync-center"})


def catalog_targets(targets: list[ResourceSyncTarget], *, output: Optional[str] = None, snapshot: bool = False,
                    config_dir: Optional[str | Path] = None, scan_catalog_func=None, write_catalog_report_func=None,
                    snapshot_catalog_func=None) -> tuple[ResourceSyncRun, CatalogReport]:
    now = _now_iso()
    items = []
    for target in targets:
        if target.enabled and target.local_dir:
            items.append((target, scan_catalog_func(target.local_dir)))
    report = _combine_catalog_reports(items)
    catalog_path = output
    if output:
        write_catalog_report_func(report, output)
    if snapshot:
        catalog_path = snapshot_catalog_func(report, history_dir=str(_catalog_dir(config_dir)))
        report.metadata["snapshot"] = catalog_path
    if output:
        report.metadata["output"] = output
    run = ResourceSyncRun(uuid.uuid4().hex, "sync-center", "catalog", "ok", now, finished_at=_now_iso(), path=catalog_path, metadata={"entries": len(report.entries)})
    append_run(run, config_dir)
    return run, report


def _resolve_targets(targets: list[ResourceSyncTarget], target_id: Optional[str] = None, all: bool = False) -> list[ResourceSyncTarget]:
    if all:
        return [target for target in targets if target.enabled]
    if target_id:
        return [target for target in targets if target.id == target_id]
    return targets


__all__ = [name for name in globals() if not name.startswith("_")]
