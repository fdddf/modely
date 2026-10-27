"""Compatibility facade for local resource sync-center helpers.

This module intentionally remains the stable monkeypatch and import surface for
sync-center behavior. Keep dependency symbols imported here so existing tests and
user code can patch ``modely.resource_sync.<dependency>`` while implementation is
incrementally split into enterprise packages.
"""

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

from .audit import record_audit_event
from .catalog import catalog_summary, scan_catalog, snapshot_catalog, write_catalog_report
from .common import cache
from .plan import create_download_plan
from .sync import sync_resource
from .types import CatalogEntry, CatalogReport, ResourceSyncRun, ResourceSyncState, ResourceSyncTarget
from .uri import parse_modely_uri
from .watch import get_remote_fingerprint
from .syncing import center as _center

SYNC_CENTER_DIRNAME = _center.SYNC_CENTER_DIRNAME
SUPPORTED_DRIFT_SOURCES = _center.SUPPORTED_DRIFT_SOURCES
SUPPORTED_DRIFT_REPO_TYPES = _center.SUPPORTED_DRIFT_REPO_TYPES

_now_iso = _center._now_iso
_sync_center_dir = _center._sync_center_dir
_targets_path = _center._targets_path
_states_path = _center._states_path
_runs_path = _center._runs_path
_catalog_dir = _center._catalog_dir
_write_json_atomic = _center._write_json_atomic
_read_json = _center._read_json
_coerce_list = _center._coerce_list
_coerce_dict = _center._coerce_dict
_target_from_dict = _center._target_from_dict
_state_from_dict = _center._state_from_dict
_run_from_dict = _center._run_from_dict
_error_run = _center._error_run
_parse_resource_defaults = _center._parse_resource_defaults
_merged_runtime_token = _center._merged_runtime_token
_plan_summary = _center._plan_summary
_sync_summary = _center._sync_summary
_catalog_entry_with_target = _center._catalog_entry_with_target
_combine_catalog_reports = _center._combine_catalog_reports
_resolve_targets = _center._resolve_targets


def default_sync_center_dir() -> Path:
    """Return the default local sync-center directory."""
    return Path(cache.CONFIG_DIR) / SYNC_CENTER_DIRNAME


def _config_dir(config_dir: Optional[str | Path] = None) -> Optional[str | Path]:
    return config_dir if config_dir is not None else default_sync_center_dir()


def make_target_id(resource: str, *, local_dir: Optional[str] = None, revision: Optional[str] = None) -> str:
    return _center.make_target_id(resource, local_dir=local_dir, revision=revision)


def load_targets(config_dir: Optional[str | Path] = None) -> list[ResourceSyncTarget]:
    return _center.load_targets(_config_dir(config_dir))


def save_targets(targets: list[ResourceSyncTarget], config_dir: Optional[str | Path] = None) -> None:
    return _center.save_targets(targets, _config_dir(config_dir))


def load_states(config_dir: Optional[str | Path] = None) -> dict[str, ResourceSyncState]:
    return _center.load_states(_config_dir(config_dir))


def save_states(states: dict[str, ResourceSyncState], config_dir: Optional[str | Path] = None) -> None:
    return _center.save_states(states, _config_dir(config_dir))


def append_run(run: ResourceSyncRun, config_dir: Optional[str | Path] = None) -> None:
    return _center.append_run(run, _config_dir(config_dir))


def list_runs(*, target_id: Optional[str] = None, limit: int = 50, config_dir: Optional[str | Path] = None) -> list[ResourceSyncRun]:
    return _center.list_runs(target_id=target_id, limit=limit, config_dir=_config_dir(config_dir))


def add_target(*args, **kwargs):
    kwargs.setdefault("record_audit_event_func", record_audit_event)
    kwargs.setdefault("default_sync_center_dir_func", default_sync_center_dir)
    kwargs["config_dir"] = _config_dir(kwargs.get("config_dir"))
    return _center.add_target(*args, **kwargs)


def list_targets(config_dir: Optional[str | Path] = None) -> list[ResourceSyncTarget]:
    return _center.list_targets(_config_dir(config_dir))


def get_target(target_id: str, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    return _center.get_target(target_id, _config_dir(config_dir))


def remove_target(target_id: str, *, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    return _center.remove_target(target_id, config_dir=_config_dir(config_dir))


def set_target_enabled(target_id: str, enabled: bool, *, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    return _center.set_target_enabled(target_id, enabled, config_dir=_config_dir(config_dir))


def enable_target(target_id: str, *, enabled: bool = True, config_dir: Optional[str | Path] = None) -> ResourceSyncTarget:
    return set_target_enabled(target_id, enabled, config_dir=config_dir)


def plan_target(target: ResourceSyncTarget, *, token: Optional[str] = None, config_dir: Optional[str | Path] = None) -> tuple[ResourceSyncRun, Any]:
    return _center.plan_target(target, token=token, config_dir=_config_dir(config_dir), create_download_plan_func=create_download_plan)


def sync_target(target: ResourceSyncTarget, *, token: Optional[str] = None, force_download: Optional[bool] = None,
                checksum: Optional[bool] = None, config_dir: Optional[str | Path] = None) -> ResourceSyncRun:
    return _center.sync_target(
        target,
        token=token,
        force_download=force_download,
        checksum=checksum,
        config_dir=_config_dir(config_dir),
        sync_resource_func=sync_resource,
    )


def check_target_drift(target: ResourceSyncTarget, *, config_dir: Optional[str | Path] = None) -> ResourceSyncRun:
    return _center.check_target_drift(target, config_dir=_config_dir(config_dir), get_remote_fingerprint_func=get_remote_fingerprint)


def catalog_targets(targets: list[ResourceSyncTarget], *, output: Optional[str] = None, snapshot: bool = False,
                    config_dir: Optional[str | Path] = None) -> tuple[ResourceSyncRun, CatalogReport]:
    return _center.catalog_targets(
        targets,
        output=output,
        snapshot=snapshot,
        config_dir=_config_dir(config_dir),
        scan_catalog_func=scan_catalog,
        write_catalog_report_func=write_catalog_report,
        snapshot_catalog_func=snapshot_catalog,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
