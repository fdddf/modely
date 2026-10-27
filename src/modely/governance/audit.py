"""Local audit log helpers for modely operations.

This module provides the canonical audit recording path for the enterprise
platform.  It uses the event type constants defined in
``modely.domain.audit_events`` and enforces redaction before storage.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..common import cache
from ..domain.audit_events import AUDIT_ACTIONS, AuditEvent, is_audit_action
from ..governance.redaction import redact_mapping

AUDIT_FILE = "audit.jsonl"


def audit_path() -> Path:
    """Return the local audit log path."""
    return Path(cache.CONFIG_DIR) / AUDIT_FILE


def record_audit_event(
    action: str,
    *,
    resource: Optional[str] = None,
    status: str = "ok",
    metadata: Optional[dict] = None,
    tenant_scope: Optional[dict[str, Any]] = None,
    actor: Optional[str] = None,
) -> dict:
    """Append one local audit event and return it.

    Parameters:
        action: Canonical audit action (e.g. ``asset.download``, ``approval.requested``).
        resource: The asset, policy profile, sync target, or other resource identifier.
        status: Short outcome — ``"ok"`` or ``"denied"``.
        metadata: Arbitrary context; sensitive fields are redacted before storage.
        tenant_scope: Optional tenant scoping dict with ``organization_id`` and
            ``workspace_id`` keys for multi-tenant deployments.
        actor: Principal identifier that triggered the event.

    Returns:
        A dictionary representing the recorded audit event (with redacted metadata).
    """
    if not is_audit_action(action):
        # Allow non-canonical actions for backward compatibility (e.g. labels, sync-center
        # callers that predate the canonical set).  Production callers should migrate.
        pass

    metadata_dict: dict[str, Any] = metadata or {}

    # Redact sensitive fields before storage
    safe_metadata = redact_mapping(metadata_dict)

    event: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "resource": resource,
        "status": status,
        "metadata": safe_metadata,
    }

    if actor is not None:
        event["actor"] = actor

    if tenant_scope is not None:
        event["tenant_scope"] = tenant_scope

    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def list_audit_events(
    *,
    limit: int = 50,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    actor: Optional[str] = None,
    tenant_scope: Optional[dict[str, Any]] = None,
) -> list[dict]:
    """Read local audit events newest first.

    Parameters:
        limit: Maximum number of events to return.
        action: Optional canonical action filter.
        resource: Optional resource filter.
        actor: Optional actor/principal filter.
        tenant_scope: Optional tenant scoping filter.  Uses partial-match
            semantics: every key present in the filter must match the
            corresponding value in the event's ``tenant_scope`` dict.
            Events without a ``tenant_scope`` are excluded when a filter
            is supplied.
    """
    path = audit_path()
    if not path.exists():
        return []

    def _tenant_scope_match(
        event_scope: Optional[dict[str, Any]],
        filter_scope: dict[str, Any],
    ) -> bool:
        """Partial-match: every key in *filter_scope* must equal the event's value."""
        if event_scope is None:
            return False
        return all(
            event_scope.get(k) == v for k, v in filter_scope.items()
        )

    events = deque(maxlen=limit)
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if action and event.get("action") != action:
                continue
            if resource and event.get("resource") != resource:
                continue
            if actor and event.get("actor") != actor:
                continue
            if tenant_scope and not _tenant_scope_match(
                event.get("tenant_scope"), tenant_scope
            ):
                continue
            events.append(event)
    return list(reversed(events))


def print_audit_events(events: list[dict], *, as_json: bool = False) -> None:
    """Print audit events."""
    if as_json:
        print(json.dumps(events, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not events:
        print("No audit events found.")
        return
    for event in events:
        resource = event.get("resource") or "-"
        actor = event.get("actor") or "-"
        status = event.get("status", "-")
        tenant = event.get("tenant_scope")
        line = f"{event.get('ts', '-')}  {event.get('action', '-')}  {status}  {resource}  {actor}"
        if tenant:
            org = tenant.get("org_id") or tenant.get("organization_id", "")
            proj = tenant.get("project_id", "")
            ws = tenant.get("workspace_id", "")
            parts = [org, proj, ws]
            scope_str = "/".join(p for p in parts if p)
            if scope_str:
                line += f"  [{scope_str}]"
        print(line)


# ---------------------------------------------------------------------------
# Convenience wrapper — single-call audit emission
# ---------------------------------------------------------------------------


def emit_audit_event(
    action: str,
    *,
    resource: str | None = None,
    status: str = "ok",
    actor: str | None = None,
    metadata: dict | None = None,
    tenant_scope: dict[str, Any] | None = None,
) -> dict:
    """Convenience wrapper around ``record_audit_event``.

    All parameters are forwarded directly to ``record_audit_event``.
    This function exists to provide a single import point for audit emission
    across governance, catalog, auth, and policy engine modules.

    Returns:
        The dictionary returned by ``record_audit_event``.
    """
    return record_audit_event(
        action,
        resource=resource,
        status=status,
        actor=actor,
        metadata=metadata,
        tenant_scope=tenant_scope,
    )


# -- Audit retention / cleanup (Phase 2f) --------------------------------------

DEFAULT_RETENTION_DAYS = 365
DEFAULT_MAX_EVENTS = 100_000


def cleanup_audit_events(
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    max_events: int = DEFAULT_MAX_EVENTS,
    dry_run: bool = True,
) -> dict:
    """Remove audit events older than *retention_days* or trim to *max_events*.

    When *dry_run* is ``True`` (default), only returns a summary without
    deleting anything.  Set *dry_run* to ``False`` to actually purge events.

    This is an **advisory** cleanup action.  It does NOT silently delete data
    without explicit opt-in.
    """

    from datetime import datetime, timedelta, timezone

    path = audit_path()
    if not path.exists():
        return {"deleted": 0, "kept": 0, "dry_run": dry_run}

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept = []
    deleted_count = 0

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                ts = event.get("ts", "")
                if ts and datetime.fromisoformat(ts) < cutoff:
                    deleted_count += 1
                else:
                    kept.append(line)
            except json.JSONDecodeError:
                kept.append(line)

    # Trim to max events (keep newest)
    if len(kept) > max_events:
        deleted_count += len(kept) - max_events
        kept = kept[-max_events:]

    if not dry_run:
        with open(path, "w") as f:
            for line in kept:
                f.write(line + "\n")

    return {"deleted": deleted_count, "kept": len(kept), "retention_days": retention_days, "dry_run": dry_run}
