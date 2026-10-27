"""Unit tests for modely.governance.audit — record, list, print, emit, and edge cases."""

import io
import json
import tempfile
from pathlib import Path

import pytest

from modely.governance.audit import (
    AUDIT_FILE,
    cleanup_audit_events,
    emit_audit_event,
    list_audit_events,
    print_audit_events,
    record_audit_event,
)
from modely.domain.audit_events import (
    AUDIT_ACCESS_BREAK_GLASS_USED,
    AUDIT_ACCESS_RESTRICTED_ATTEMPT,
    AUDIT_ADMIN_ASSET_DELETED,
    AUDIT_ADMIN_QUOTA_CHANGED,
    AUDIT_ADMIN_ROLE_ASSIGNED,
    AUDIT_ADMIN_ROLE_REVOKED,
    AUDIT_ADMIN_TEAM_CREATED,
    AUDIT_APPROVAL_APPROVED,
    AUDIT_APPROVAL_CANCELLED,
    AUDIT_APPROVAL_ESCALATED,
    AUDIT_APPROVAL_EXPIRED,
    AUDIT_APPROVAL_REJECTED,
    AUDIT_APPROVAL_REQUESTED,
    AUDIT_AUTH_LOGIN,
    AUDIT_AUTH_LOGIN_FAILED,
    AUDIT_AUTH_LOGOUT,
    AUDIT_CATALOG_ASSET_SEARCH,
    AUDIT_CATALOG_ASSET_VIEW,
    AUDIT_CREDENTIAL_CREATED,
    AUDIT_CREDENTIAL_FAILED,
    AUDIT_CREDENTIAL_REVOKED,
    AUDIT_CREDENTIAL_ROTATED,
    AUDIT_CREDENTIAL_USED,
    AUDIT_DOWNLOAD,
    AUDIT_DOWNLOAD_DENIED,
    AUDIT_DOWNLOAD_URL_ISSUED,
    AUDIT_POLICY_CHANGED,
    AUDIT_POLICY_EVALUATED,
    AUDIT_POLICY_PROFILE_ARCHIVED,
    AUDIT_POLICY_PROFILE_CREATED,
    AUDIT_POLICY_PROFILE_UPDATED,
    AUDIT_REPORT_EXPORTED,
    AUDIT_SYNC_JOB_CREATED,
    AUDIT_SYNC_JOB_FAILED,
    AUDIT_SYNC_JOB_STARTED,
    AUDIT_SYNC_JOB_SUCCEEDED,
    AUDIT_TOKEN_ISSUED,
    AUDIT_TOKEN_REVOKED,
    AUDIT_TOKEN_ROTATED,
)

# Every canonical audit action constant for exhaustive testing
ALL_AUDIT_ACTIONS = [
    # Auth
    AUDIT_AUTH_LOGIN,
    AUDIT_AUTH_LOGIN_FAILED,
    AUDIT_AUTH_LOGOUT,
    # Catalog
    AUDIT_CATALOG_ASSET_VIEW,
    AUDIT_CATALOG_ASSET_SEARCH,
    # Download
    AUDIT_DOWNLOAD,
    AUDIT_DOWNLOAD_DENIED,
    AUDIT_DOWNLOAD_URL_ISSUED,
    # Sync
    AUDIT_SYNC_JOB_CREATED,
    AUDIT_SYNC_JOB_STARTED,
    AUDIT_SYNC_JOB_SUCCEEDED,
    AUDIT_SYNC_JOB_FAILED,
    # Policy
    AUDIT_POLICY_EVALUATED,
    AUDIT_POLICY_CHANGED,
    AUDIT_POLICY_PROFILE_CREATED,
    AUDIT_POLICY_PROFILE_UPDATED,
    AUDIT_POLICY_PROFILE_ARCHIVED,
    # Approval
    AUDIT_APPROVAL_REQUESTED,
    AUDIT_APPROVAL_APPROVED,
    AUDIT_APPROVAL_REJECTED,
    AUDIT_APPROVAL_CANCELLED,
    AUDIT_APPROVAL_EXPIRED,
    AUDIT_APPROVAL_ESCALATED,
    # Admin
    AUDIT_ADMIN_ROLE_ASSIGNED,
    AUDIT_ADMIN_ROLE_REVOKED,
    AUDIT_ADMIN_TEAM_CREATED,
    AUDIT_ADMIN_ASSET_DELETED,
    AUDIT_ADMIN_QUOTA_CHANGED,
    # Restricted / break-glass
    AUDIT_ACCESS_RESTRICTED_ATTEMPT,
    AUDIT_ACCESS_BREAK_GLASS_USED,
    # Report
    AUDIT_REPORT_EXPORTED,
    # Phase 3 reserved — token
    AUDIT_TOKEN_ISSUED,
    AUDIT_TOKEN_REVOKED,
    AUDIT_TOKEN_ROTATED,
    # Credential lifecycle
    AUDIT_CREDENTIAL_CREATED,
    AUDIT_CREDENTIAL_FAILED,
    AUDIT_CREDENTIAL_REVOKED,
    AUDIT_CREDENTIAL_ROTATED,
    AUDIT_CREDENTIAL_USED,
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _event_count(path: Path) -> int:
    """Return the number of non-empty JSONL lines in an audit file."""
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            count += 1
        except json.JSONDecodeError:
            pass
    return count


# ---------------------------------------------------------------------------
# 1. record_audit_event() — all canonical action types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", ALL_AUDIT_ACTIONS)
def test_record_audit_event_all_actions(action, tmp_path, monkeypatch):
    """Every canonical AUDIT_* action records and produces a valid event."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    event = record_audit_event(action, resource="res-1", actor="user-1")

    assert event["action"] == action
    assert event["resource"] == "res-1"
    assert event["actor"] == "user-1"
    assert event["status"] == "ok"
    assert "ts" in event
    assert "metadata" in event


# ---------------------------------------------------------------------------
# 2. record_audit_event() — with tenant_scope, with metadata (redaction)
# ---------------------------------------------------------------------------

def test_record_audit_event_with_tenant_scope(tmp_path, monkeypatch):
    """Tenant scoping is embedded in the stored event."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    event = record_audit_event(
        AUDIT_SYNC_JOB_CREATED,
        resource="target-1",
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1"},
    )

    assert event["tenant_scope"]["organization_id"] == "org-1"
    assert event["tenant_scope"]["workspace_id"] == "ws-1"


def test_record_audit_event_redacts_metadata(tmp_path, monkeypatch):
    """Metadata with sensitive fields is redacted before storage."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    event = record_audit_event(
        AUDIT_AUTH_LOGIN,
        resource="user-1",
        metadata={
            "token": "very-secret",
            "password": "pass123",
            "private_key": "key-data",
            "username": "alice",
            "safe_field": "ok",
        },
    )

    assert event["metadata"]["token"] == "<redacted>"
    assert event["metadata"]["password"] == "<redacted>"
    assert event["metadata"]["private_key"] == "<redacted>"
    assert event["metadata"]["username"] == "alice"
    assert event["metadata"]["safe_field"] == "ok"


def test_record_audit_event_redacts_nested_metadata(tmp_path, monkeypatch):
    """Nested metadata dicts are recursively redacted."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    event = record_audit_event(
        AUDIT_ADMIN_ROLE_ASSIGNED,
        resource="role-1",
        metadata={
            "credential": {"token": "nested-secret", "type": "api_key"},
            "tags": ["public", "confidential"],
        },
    )

    # Top-level "credential" is a sensitive field name -> fully redacted
    assert event["metadata"]["credential"] == "<redacted>"
    assert event["metadata"]["tags"] == ["public", "confidential"]


def test_record_audit_event_redacts_token_in_string_values(tmp_path, monkeypatch):
    """Token-like patterns in string values are redacted."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    event = record_audit_event(
        AUDIT_CREDENTIAL_USED,
        resource="cred-1",
        metadata={"url": "https://example.com?token=abc123&other=val"},
    )

    assert "token=<redacted>" in event["metadata"]["url"]
    assert "other=val" in event["metadata"]["url"]


# ---------------------------------------------------------------------------
# 3. list_audit_events() — filter by action, resource, limit
# ---------------------------------------------------------------------------

def test_list_audit_events_filter_by_action(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    record_audit_event(AUDIT_DOWNLOAD, resource="a")
    record_audit_event(AUDIT_POLICY_CHANGED, resource="b")
    record_audit_event(AUDIT_DOWNLOAD, resource="c")

    downloads = list_audit_events(action=AUDIT_DOWNLOAD)
    assert len(downloads) == 2
    assert all(e["action"] == AUDIT_DOWNLOAD for e in downloads)


def test_list_audit_events_filter_by_resource(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    record_audit_event(AUDIT_DOWNLOAD, resource="model-a")
    record_audit_event(AUDIT_DOWNLOAD, resource="model-b")
    record_audit_event(AUDIT_DOWNLOAD, resource="model-a")

    filtered = list_audit_events(resource="model-a")
    assert len(filtered) == 2
    assert all(e["resource"] == "model-a" for e in filtered)


def test_list_audit_events_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    for i in range(10):
        record_audit_event(AUDIT_CATALOG_ASSET_VIEW, resource=f"asset-{i}")

    events = list_audit_events(limit=3)
    assert len(events) == 3
    # Newest first
    assert events[0]["resource"] == "asset-9"
    assert events[1]["resource"] == "asset-8"
    assert events[2]["resource"] == "asset-7"


# ---------------------------------------------------------------------------
# 4. list_audit_events() — empty result when no events match
# ---------------------------------------------------------------------------

def test_list_audit_events_empty_when_no_events_match(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    record_audit_event(AUDIT_DOWNLOAD, resource="a")
    record_audit_event(AUDIT_DOWNLOAD, resource="b")

    events = list_audit_events(action=AUDIT_ADMIN_ROLE_ASSIGNED)
    assert events == []

    events = list_audit_events(resource="nonexistent")
    assert events == []


# ---------------------------------------------------------------------------
# 5. list_audit_events() — tenant_scope filtering
# ---------------------------------------------------------------------------

def test_list_audit_events_tenant_scope_partial_match(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    record_audit_event(
        AUDIT_SYNC_JOB_CREATED,
        resource="target-1",
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-a"},
    )
    record_audit_event(
        AUDIT_SYNC_JOB_CREATED,
        resource="target-2",
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-b"},
    )
    record_audit_event(
        AUDIT_SYNC_JOB_CREATED,
        resource="target-3",
        tenant_scope={"organization_id": "org-2", "workspace_id": "ws-a"},
    )

    # Partial match on organization_id only
    org1 = list_audit_events(
        action=AUDIT_SYNC_JOB_CREATED,
        tenant_scope={"organization_id": "org-1"},
    )
    assert len(org1) == 2
    assert all(e["tenant_scope"]["organization_id"] == "org-1" for e in org1)

    # Full match
    full = list_audit_events(
        action=AUDIT_SYNC_JOB_CREATED,
        tenant_scope={"organization_id": "org-2", "workspace_id": "ws-a"},
    )
    assert len(full) == 1
    assert full[0]["resource"] == "target-3"


def test_list_audit_events_tenant_scope_excludes_events_without_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    record_audit_event(AUDIT_DOWNLOAD, resource="unscoped")  # no tenant_scope
    record_audit_event(
        AUDIT_DOWNLOAD,
        resource="scoped",
        tenant_scope={"organization_id": "org-1"},
    )

    # Without tenant_scope filter, both appear
    all_events = list_audit_events()
    assert len(all_events) == 2

    # With tenant_scope filter, only the scoped one appears
    scoped = list_audit_events(tenant_scope={"organization_id": "org-1"})
    assert len(scoped) == 1
    assert scoped[0]["resource"] == "scoped"


# ---------------------------------------------------------------------------
# 6. print_audit_events() — json and human-readable modes
# ---------------------------------------------------------------------------

def test_print_audit_events_json_mode(capsys):
    events = [
        {
            "ts": "2026-01-01T00:00:00+00:00",
            "action": AUDIT_DOWNLOAD,
            "status": "ok",
            "resource": "model-a",
            "actor": "user-1",
            "metadata": {},
        }
    ]
    print_audit_events(events, as_json=True)
    captured = capsys.readouterr().out

    parsed = json.loads(captured)
    assert len(parsed) == 1
    assert parsed[0]["action"] == AUDIT_DOWNLOAD
    assert parsed[0]["resource"] == "model-a"


def test_print_audit_events_human_readable(capsys):
    events = [
        {
            "ts": "2026-01-01T00:00:00+00:00",
            "action": AUDIT_DOWNLOAD,
            "status": "ok",
            "resource": "model-a",
            "actor": "user-1",
            "metadata": {},
        }
    ]
    print_audit_events(events, as_json=False)
    captured = capsys.readouterr().out

    assert AUDIT_DOWNLOAD in captured
    assert "model-a" in captured
    assert "user-1" in captured
    assert "ok" in captured


def test_print_audit_events_human_no_events(capsys):
    print_audit_events([], as_json=False)
    captured = capsys.readouterr().out
    assert "No audit events found." in captured


def test_print_audit_events_json_empty(capsys):
    print_audit_events([], as_json=True)
    captured = capsys.readouterr().out
    assert json.loads(captured) == []


def test_print_audit_events_human_with_tenant_scope(capsys):
    events = [
        {
            "ts": "2026-01-01T00:00:00+00:00",
            "action": AUDIT_SYNC_JOB_STARTED,
            "status": "ok",
            "resource": "target-1",
            "actor": "svc",
            "tenant_scope": {"organization_id": "org-1", "workspace_id": "ws-1"},
            "metadata": {},
        }
    ]
    print_audit_events(events, as_json=False)
    captured = capsys.readouterr().out
    # Should include tenant scope breadcrumb
    assert "[org-1/ws-1]" in captured


def test_print_audit_events_tenant_scope_uses_alternative_keys(capsys):
    """print_audit_events falls back to org_id and project_id when present."""
    events = [
        {
            "ts": "2026-01-01T00:00:00+00:00",
            "action": AUDIT_SYNC_JOB_FAILED,
            "status": "denied",
            "resource": "target-2",
            "actor": "admin",
            "tenant_scope": {"org_id": "org-2", "project_id": "proj-1", "workspace_id": "ws-2"},
            "metadata": {},
        }
    ]
    print_audit_events(events, as_json=False)
    captured = capsys.readouterr().out
    assert "[org-2/proj-1/ws-2]" in captured


# ---------------------------------------------------------------------------
# 7. emit_audit_event() wrapper
# ---------------------------------------------------------------------------

def test_emit_audit_event_is_identical_to_record(tmp_path, monkeypatch):
    """emit_audit_event produces the same result as record_audit_event."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "audit_emit.jsonl")

    event = emit_audit_event(
        AUDIT_APPROVAL_APPROVED,
        resource="res-1",
        status="ok",
        actor="approver-1",
        metadata={"note": "approved after review"},
        tenant_scope={"organization_id": "org-1"},
    )

    assert event["action"] == AUDIT_APPROVAL_APPROVED
    assert event["resource"] == "res-1"
    assert event["actor"] == "approver-1"
    assert event["tenant_scope"]["organization_id"] == "org-1"
    assert event["metadata"]["note"] == "approved after review"

    # Verify it was persisted
    events = list_audit_events(action=AUDIT_APPROVAL_APPROVED)
    assert len(events) == 1


def test_emit_audit_event_default_status(tmp_path, monkeypatch):
    """emit_audit_event defaults status to "ok"."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / AUDIT_FILE)

    event = emit_audit_event(AUDIT_REPORT_EXPORTED, resource="report-1")
    assert event["status"] == "ok"


# ---------------------------------------------------------------------------
# 8. Edge case: empty / no audit log file
# ---------------------------------------------------------------------------

def test_list_audit_events_no_file_at_all(tmp_path, monkeypatch):
    """When no audit file exists, list returns empty list."""
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "nonexistent" / AUDIT_FILE)
    events = list_audit_events()
    assert events == []


def test_list_audit_events_empty_file(tmp_path, monkeypatch):
    """An empty audit file yields an empty list."""
    audit_file = tmp_path / AUDIT_FILE
    audit_file.write_text("")
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: audit_file)
    events = list_audit_events()
    assert events == []


def test_list_audit_events_skips_malformed_json(tmp_path, monkeypatch):
    """Malformed JSON lines are silently skipped."""
    audit_file = tmp_path / AUDIT_FILE
    audit_file.write_text(
        '{"ts": "2026-01-01", "action": "asset.download", "status": "ok", "resource": "good", "metadata": {}}\n'
        "this is not json\n"
        '{"ts": "2026-01-02", "action": "asset.view", "status": "ok", "resource": "good2", "metadata": {}}\n'
    )
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: audit_file)
    events = list_audit_events()
    assert len(events) == 2
    assert events[0]["action"] == "asset.view"  # newest first
    assert events[1]["action"] == "asset.download"


# ---------------------------------------------------------------------------
# cleanup_audit_events edge cases
# ---------------------------------------------------------------------------

def test_cleanup_audit_events_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "does_not_exist" / AUDIT_FILE)
    result = cleanup_audit_events(dry_run=False)
    assert result["deleted"] == 0
    assert result["kept"] == 0


def test_cleanup_audit_events_dry_run_is_safe(tmp_path, monkeypatch):
    """Dry run reports what would be deleted but does not mutate the file."""
    audit_file = tmp_path / AUDIT_FILE
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: audit_file)

    for i in range(5):
        record_audit_event(AUDIT_CATALOG_ASSET_VIEW, resource=f"asset-{i}")

    before_count = _event_count(audit_file)
    result = cleanup_audit_events(retention_days=0, dry_run=True)
    after_count = _event_count(audit_file)

    # Dry run reports what would happen but does not mutate
    assert result["dry_run"] is True
    assert before_count == after_count


def test_cleanup_audit_events_retention_cutoff(tmp_path, monkeypatch):
    """Events older than retention_days are removed when dry_run=False."""
    audit_file = tmp_path / AUDIT_FILE
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: audit_file)

    # Write an event with an old timestamp directly to avoid relying on datetime.now()
    old_event = {
        "ts": "2020-01-01T00:00:00+00:00",
        "action": AUDIT_DOWNLOAD,
        "status": "ok",
        "resource": "old",
        "metadata": {},
    }
    recent_event = {
        "ts": "2099-01-01T00:00:00+00:00",
        "action": AUDIT_CATALOG_ASSET_VIEW,
        "status": "ok",
        "resource": "future",
        "metadata": {},
    }

    audit_file.write_text(
        json.dumps(old_event, sort_keys=True) + "\n" +
        json.dumps(recent_event, sort_keys=True) + "\n"
    )

    result = cleanup_audit_events(retention_days=365, dry_run=False)
    assert result["deleted"] == 1
    assert result["kept"] == 1

    # Verify only recent event remains in the file
    events = list_audit_events()
    assert len(events) == 1
    assert events[0]["resource"] == "future"


def test_cleanup_audit_events_max_events_trim(tmp_path, monkeypatch):
    """When events exceed max_events, oldest are trimmed."""
    audit_file = tmp_path / AUDIT_FILE
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: audit_file)

    for i in range(10):
        record_audit_event(AUDIT_CATALOG_ASSET_VIEW, resource=f"asset-{i}")

    result = cleanup_audit_events(max_events=3, dry_run=False)
    assert result["kept"] == 3
    assert result["deleted"] >= 7  # writes happen close together, may be within retention

    events = list_audit_events()
    assert len(events) == 3
    # Newest events are kept
    resources = [e["resource"] for e in events]
    assert "asset-9" in resources
    assert "asset-8" in resources
    assert "asset-7" in resources
