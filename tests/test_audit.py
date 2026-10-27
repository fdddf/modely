"""Unit tests for local audit logging."""

from modely.audit import list_audit_events, record_audit_event


def test_record_and_list_audit_events(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "audit.jsonl")

    record_audit_event("download.plan", resource="hf:model:gpt2")
    record_audit_event("label.set", resource="hf:model:gpt2", metadata={"tags": ["prod"]})

    events = list_audit_events(action="label.set")

    assert len(events) == 1
    assert events[0]["action"] == "label.set"
    assert events[0]["resource"] == "hf:model:gpt2"
    assert events[0]["metadata"]["tags"] == ["prod"]


def test_record_audit_event_with_canonical_action(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "audit.jsonl")

    from modely.domain.audit_events import AUDIT_DOWNLOAD

    record_audit_event(
        AUDIT_DOWNLOAD,
        resource="asset-1",
        actor="user-1",
        metadata={"file": "model.bin", "size": 1024},
    )

    events = list_audit_events(action=AUDIT_DOWNLOAD)
    assert len(events) == 1
    assert events[0]["action"] == AUDIT_DOWNLOAD
    assert events[0]["actor"] == "user-1"
    assert events[0]["resource"] == "asset-1"
    assert events[0]["metadata"]["size"] == 1024


def test_record_audit_event_with_tenant_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "audit.jsonl")

    from modely.domain.audit_events import AUDIT_SYNC_JOB_CREATED

    record_audit_event(
        AUDIT_SYNC_JOB_CREATED,
        resource="sync-target-1",
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1"},
        actor="svc-sync",
    )

    # Without tenant_scope filter, the event should still appear
    events = list_audit_events(action=AUDIT_SYNC_JOB_CREATED)
    assert len(events) == 1
    assert events[0]["tenant_scope"]["organization_id"] == "org-1"
    assert events[0]["tenant_scope"]["workspace_id"] == "ws-1"

    # With matching tenant_scope filter
    events_scoped = list_audit_events(
        action=AUDIT_SYNC_JOB_CREATED,
        tenant_scope={"organization_id": "org-1"},
    )
    assert len(events_scoped) == 1

    # With non-matching tenant_scope filter — should be empty
    events_mismatch = list_audit_events(
        action=AUDIT_SYNC_JOB_CREATED,
        tenant_scope={"organization_id": "org-2"},
    )
    assert len(events_mismatch) == 0


def test_audit_redaction(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.governance.audit.audit_path", lambda: tmp_path / "audit.jsonl")

    from modely.domain.audit_events import AUDIT_AUTH_LOGIN

    record_audit_event(
        AUDIT_AUTH_LOGIN,
        resource="user-1",
        metadata={"token": "secret-value-123", "username": "alice"},
    )

    events = list_audit_events(action=AUDIT_AUTH_LOGIN)
    assert len(events) == 1
    assert events[0]["metadata"]["token"] == "<redacted>"
    assert events[0]["metadata"]["username"] == "alice"


def test_audit_event_dto_to_dict():
    from modely.domain.audit_events import AUDIT_DOWNLOAD, AuditEvent

    event = AuditEvent(
        action=AUDIT_DOWNLOAD,
        actor="user-1",
        resource="asset-1",
        metadata={"token": "secret", "file": "model.bin"},
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1"},
    )

    # Without redaction
    d = event.to_dict()
    assert d["action"] == AUDIT_DOWNLOAD
    assert d["metadata"]["token"] == "secret"
    assert d["tenant_scope"]["organization_id"] == "org-1"

    # With redaction
    d_redacted = event.to_dict(redact=True)
    assert d_redacted["metadata"]["token"] == "<redacted>"
    assert d_redacted["metadata"]["file"] == "model.bin"


def test_is_audit_action():
    from modely.domain.audit_events import (
        AUDIT_DOWNLOAD,
        AUDIT_SYNC_JOB_CREATED,
        AUDIT_TOKEN_ISSUED,
        is_audit_action,
    )

    assert is_audit_action(AUDIT_DOWNLOAD)
    assert is_audit_action(AUDIT_SYNC_JOB_CREATED)
    assert is_audit_action(AUDIT_TOKEN_ISSUED)
    assert not is_audit_action("some.unknown.action")
    assert not is_audit_action("")


def test_is_security_sensitive_action():
    from modely.domain.audit_events import (
        AUDIT_AUTH_LOGIN_FAILED,
        AUDIT_ACCESS_BREAK_GLASS_USED,
        AUDIT_DOWNLOAD,
        is_security_sensitive_action,
    )

    assert is_security_sensitive_action(AUDIT_AUTH_LOGIN_FAILED)
    assert is_security_sensitive_action(AUDIT_ACCESS_BREAK_GLASS_USED)
    assert not is_security_sensitive_action(AUDIT_DOWNLOAD)


def test_all_canonical_actions_are_valid():
    """Every constant in AUDIT_ACTIONS must be recognized by is_audit_action."""
    from modely.domain.audit_events import AUDIT_ACTIONS, is_audit_action

    for action in AUDIT_ACTIONS:
        assert is_audit_action(action), f"Action not recognized: {action}"


def test_to_dict_roundtrip_preserves_core_fields():
    from modely.domain.audit_events import AUDIT_APPROVAL_REQUESTED, AuditEvent

    event = AuditEvent(
        action=AUDIT_APPROVAL_REQUESTED,
        actor="approver-1",
        resource="asset-99",
        created_at="2026-01-01T00:00:00Z",
        outcome="ok",
        metadata={"request_id": "req-1"},
        tenant_scope={"organization_id": "org-1", "workspace_id": "ws-1"},
    )
    d = event.to_dict()
    assert d["action"] == AUDIT_APPROVAL_REQUESTED
    assert d["actor"] == "approver-1"
    assert d["resource"] == "asset-99"
    assert d["created_at"] == "2026-01-01T00:00:00Z"
    assert d["outcome"] == "ok"
    assert d["tenant_scope"]["workspace_id"] == "ws-1"
