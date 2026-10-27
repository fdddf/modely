"""Application services for the local resource sync center."""

from __future__ import annotations

from typing import Optional

from .. import resource_sync as sync_center_facade
from ..syncing import center as sync_center_store
from ..types import SyncCenterReport

create_download_plan = None
sync_resource = None
get_remote_fingerprint = None
scan_catalog = None
write_catalog_report = None
snapshot_catalog = None


def _dependency(name: str):
    value = globals().get(name)
    return value if value is not None else getattr(sync_center_facade, name)


def _config_dir(config_dir=None):
    return config_dir if config_dir is not None else sync_center_facade.default_sync_center_dir()


def _states_for_targets(targets, config_dir=None):
    states = sync_center_store.load_states(_config_dir(config_dir))
    return {target.id: states[target.id] for target in targets if target.id in states}


def _report_for_targets(targets, *, runs=None, summary=None, warnings=None, metadata=None, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    return SyncCenterReport(
        targets=list(targets),
        states=_states_for_targets(targets, config_dir),
        runs=list(runs or []),
        summary=dict(summary or {}),
        warnings=list(warnings or []),
        metadata=dict(metadata or {}),
    )


def _load_report(config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    targets = sync_center_store.load_targets(config_dir)
    return _report_for_targets(
        targets,
        summary={"targets": len(targets), "enabled": sum(1 for target in targets if target.enabled)},
        config_dir=config_dir,
    )


def _select_targets(target_id: Optional[str], all: bool, config_dir=None):
    config_dir = _config_dir(config_dir)
    targets = sync_center_store.load_targets(config_dir)
    if all:
        return [target for target in targets if target.enabled]
    if not target_id:
        raise ValueError("Specify a target ID or --all")
    return [sync_center_store.get_target(target_id, config_dir=config_dir)]


def add_sync_target(**kwargs) -> SyncCenterReport:
    config_dir = _config_dir(kwargs.pop("config_dir", None))
    target = sync_center_store.add_target(**kwargs, config_dir=config_dir)
    return _report_for_targets([target], summary={"targets": 1, "enabled": 1}, config_dir=config_dir)


def list_sync_targets(*, config_dir=None) -> SyncCenterReport:
    return _load_report(config_dir)


def show_sync_target(target_id: str, *, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    target = sync_center_store.get_target(target_id, config_dir=config_dir)
    return _report_for_targets([target], summary={"targets": 1, "enabled": 1 if target.enabled else 0}, config_dir=config_dir)


def remove_sync_target(target_id: str, *, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    target = sync_center_store.remove_target(target_id, config_dir=config_dir)
    return SyncCenterReport(targets=[target], states={}, summary={"removed": 1})


def set_sync_target_enabled(target_id: str, enabled: bool, *, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    target = sync_center_store.enable_target(target_id, enabled=enabled, config_dir=config_dir)
    return _report_for_targets([target], summary={"enabled": enabled}, config_dir=config_dir)


def list_sync_runs(*, target_id: Optional[str] = None, limit: int = 50, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    runs = sync_center_store.list_runs(limit=limit, target_id=target_id, config_dir=config_dir)
    return SyncCenterReport(runs=runs, summary={"runs": len(runs)})


def plan_sync_targets(*, target_id: Optional[str] = None, all: bool = False, token: Optional[str] = None, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    targets = _select_targets(target_id, all, config_dir)
    runs = []
    warnings = []
    plans = []
    for target in targets:
        try:
            run, plan = sync_center_store.plan_target(target, token=token, config_dir=config_dir, create_download_plan_func=_dependency("create_download_plan"))
            runs.append(run)
            plans.append(plan.to_dict())
        except Exception as exc:
            warnings.append(f"{target.id}: {exc}")
    return _report_for_targets(
        targets,
        runs=runs,
        summary={"targets": len(targets), "plans": len(plans), "errors": len(warnings)},
        warnings=warnings,
        metadata={"plans": plans},
        config_dir=config_dir,
    )


def run_sync_targets(
    *,
    target_id: Optional[str] = None,
    all: bool = False,
    token: Optional[str] = None,
    force_download: Optional[bool] = None,
    checksum: Optional[bool] = None,
    config_dir=None,
) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    targets = _select_targets(target_id, all, config_dir)
    runs = []
    warnings = []
    for target in targets:
        run = sync_center_store.sync_target(
            target,
            token=token,
            force_download=force_download,
            checksum=checksum,
            config_dir=config_dir,
            sync_resource_func=_dependency("sync_resource"),
        )
        runs.append(run)
        if run.status == "error":
            warnings.append(f"{target.id}: {run.error}")
    return _report_for_targets(
        targets,
        runs=runs,
        summary={"targets": len(targets), "ok": sum(1 for run in runs if run.status == "ok"), "errors": sum(1 for run in runs if run.status == "error")},
        warnings=warnings,
        config_dir=config_dir,
    )


def check_sync_targets(*, target_id: Optional[str] = None, all: bool = False, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    targets = _select_targets(target_id, all, config_dir)
    runs = [sync_center_store.check_target_drift(target, config_dir=config_dir, get_remote_fingerprint_func=_dependency("get_remote_fingerprint")) for target in targets]
    return _report_for_targets(
        targets,
        runs=runs,
        summary={
            "targets": len(targets),
            "drifted": sum(1 for run in runs if run.status == "drifted"),
            "unchanged": sum(1 for run in runs if run.status == "unchanged"),
            "unsupported": sum(1 for run in runs if run.status == "unsupported"),
            "errors": sum(1 for run in runs if run.status == "error"),
        },
        warnings=[warning for run in runs for warning in run.warnings],
        config_dir=config_dir,
    )


def catalog_sync_targets(*, output: Optional[str] = None, snapshot: bool = False, config_dir=None) -> SyncCenterReport:
    config_dir = _config_dir(config_dir)
    targets = sync_center_store.load_targets(config_dir)
    run, catalog = sync_center_store.catalog_targets(
        targets,
        output=output,
        snapshot=snapshot,
        config_dir=config_dir,
        scan_catalog_func=_dependency("scan_catalog"),
        write_catalog_report_func=_dependency("write_catalog_report"),
        snapshot_catalog_func=_dependency("snapshot_catalog"),
    )
    return _report_for_targets(
        targets,
        runs=[run],
        summary={"targets": catalog.summary.get("targets", 0), "entries": len(catalog.entries)},
        warnings=catalog.warnings,
        metadata={"catalog": catalog.to_dict()},
        config_dir=config_dir,
    )
