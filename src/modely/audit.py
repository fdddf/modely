"""Local audit log helpers for modely operations — flat compatibility facade.

This module re-exports the canonical audit functions from
``modely.governance.audit``.  It preserves the original import paths so that
existing callers (resource_sync, cataloging/labels, cli/handlers) do not break.

New callers should prefer importing from ``modely.governance.audit`` directly.
"""

from __future__ import annotations

from .governance.audit import audit_path, list_audit_events, print_audit_events, record_audit_event

__all__ = [
    "audit_path",
    "list_audit_events",
    "print_audit_events",
    "record_audit_event",
]
