"""Tests for Phase 3c-3: Enterprise Python SDK client."""

from __future__ import annotations

import pytest

from modely.enterprise_client import (
    ApprovalRequiredError,
    AuthError,
    Client,
    NotFoundError,
    PermissionDeniedError,
    PolicyBlockedError,
    ValidationError,
)


class FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


class FakeTransport:
    """Fake HTTP transport for SDK tests — no real server needed."""

    def __init__(self, responses: dict | None = None):
        self.responses = responses or {}

    def request(self, method, url, **kwargs):
        key = f"{method} {url}"
        status, data = 200, {"data": {"ok": True}, "meta": {"request_id": "req_test", "schema_version": "v1", "pagination": None}}
        if key in self.responses:
            status, data = self.responses[key]
        return FakeResponse(status, data)


def test_client_construction():
    client = Client("http://localhost:8000", token="mod-test123")
    assert client._base == "http://localhost:8000"


def test_client_error_handling():
    transport = FakeTransport({
        "GET http://localhost:8000/api/v1/assets/nonexistent": (404, {"error": {"code": "not_found", "message": "Asset not found", "request_id": "req_1", "details": {}}}),
    })
    client = Client("http://localhost:8000", _transport=transport)

    with pytest.raises(NotFoundError, match="Asset not found"):
        client.assets.get("nonexistent")


def test_client_permission_denied():
    transport = FakeTransport({
        "GET http://localhost:8000/api/v1/assets/restricted": (403, {"error": {"code": "permission_denied", "message": "Access denied", "request_id": "req_2"}}),
    })
    client = Client("http://localhost:8000", _transport=transport)

    with pytest.raises(PermissionDeniedError, match="Access denied"):
        client.assets.get("restricted")


def test_client_policy_blocked():
    transport = FakeTransport({
        "POST http://localhost:8000/api/v1/lockfiles/validate": (403, {"error": {"code": "policy_blocked", "message": "Blocked by policy", "request_id": "req_3"}}),
    })
    client = Client("http://localhost:8000", _transport=transport)

    with pytest.raises(PolicyBlockedError, match="Blocked by policy"):
        client.lockfiles.validate("/tmp/test.lock")


def test_client_validation_error():
    transport = FakeTransport({
        "POST http://localhost:8000/api/v1/lockfiles/validate": (400, {"error": {"code": "validation_error", "message": "Missing field", "request_id": "req_4"}}),
    })
    client = Client("http://localhost:8000", _transport=transport)

    with pytest.raises(ValidationError, match="Missing field"):
        client.lockfiles.validate("/tmp/test.lock")
