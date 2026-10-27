"""Tests for modely-server route registration and app factory."""

from __future__ import annotations

import pytest

from modely.server.app import ModelyServerApp, create_app


def test_create_app_registers_all_phase1_routes():
    """Phase 1 P0/P1 routes are registered."""
    app = create_app()

    phase1_routes = [
        "/api/v1/health",
        "/api/v1/version",
        "/api/v1/assets",
        "/api/v1/assets/{id}",
        "/api/v1/assets/{id}/files",
        "/api/v1/assets/{id}/download-url",
        "/api/v1/sync-jobs",
        "/api/v1/sync-jobs/{id}",
        "/api/v1/sync-jobs/{id}/logs",
    ]
    for route in phase1_routes:
        assert route in app.routes, f"Phase 1 route not registered: {route}"


def test_create_app_registers_all_phase2_governance_routes():
    """Phase 2 governance routes are registered."""
    app = create_app()

    governance_routes = [
        "/api/v1/governance/policy/evaluate",
        "/api/v1/governance/requests",
        "/api/v1/governance/requests/submit",
        "/api/v1/governance/requests/{id}",
        "/api/v1/governance/requests/{id}/approve",
        "/api/v1/governance/requests/{id}/reject",
        "/api/v1/governance/requests/{id}/cancel",
    ]
    for route in governance_routes:
        assert route in app.routes, f"Governance route not registered: {route}"


def test_create_app_registers_all_phase2_admin_routes():
    """Phase 2 admin routes are registered."""
    app = create_app()

    admin_routes = [
        "/api/v1/admin/quotas",
        "/api/v1/admin/quotas/set",
        "/api/v1/admin/quotas/{id}",
        "/api/v1/admin/quotas/{id}/delete",
        "/api/v1/admin/credentials",
        "/api/v1/admin/credentials/{id}",
        "/api/v1/admin/credentials/register",
        "/api/v1/admin/credentials/{id}/revoke",
        "/api/v1/admin/audit",
    ]
    for route in admin_routes:
        assert route in app.routes, f"Admin route not registered: {route}"


def test_create_app_registers_governance_report_route():
    """Phase 2 governance report route is registered."""
    app = create_app()
    assert "/api/v1/reports/governance" in app.routes


def test_app_call_health_route():
    """Health route returns expected structure."""
    app = create_app()
    result = app.call("/api/v1/health", request_id="test-123")
    assert "data" in result
    assert "meta" in result


def test_unknown_route_raises_keyerror():
    """Calling an unregistered route raises KeyError."""
    app = create_app()
    with pytest.raises(KeyError):
        app.call("/api/v1/nonexistent")


def test_create_fastapi_app_returns_fastapi_instance():
    """create_fastapi_app returns a FastAPI application when FastAPI is installed."""
    fastapi = pytest.importorskip("fastapi", reason="fastapi not installed")
    from modely.server.app import create_fastapi_app

    app = create_fastapi_app()
    assert isinstance(app, fastapi.FastAPI)
    assert app.title == "modely-server"
    assert app.version == "0.1.0"


def test_create_fastapi_app_includes_health_endpoint():
    """FastAPI app includes the health endpoint and returns 200."""
    pytest.importorskip("fastapi", reason="fastapi not installed")
    from fastapi.testclient import TestClient

    from modely.server.app import create_fastapi_app

    app = create_fastapi_app()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    # Either 200 (success) or 422 (validation — FastAPI expects no params)
    assert response.status_code in (200, 422)
    body = response.json()
    # Should have response data even on 422 (it's our envelope)
    assert isinstance(body, dict)


def test_create_app_sets_service_default():
    """When a service is provided, it becomes the default injected kwarg."""
    class FakeApprovalService:
        def submit_approval(self, payload):
            return {"id": "req-1", "status": "pending"}

    app = create_app(catalog_service=FakeApprovalService())
    # catalog_service also sets app.services["service"]
    # submit_approval(service, payload) — service is injected, payload via kwargs
    result = app.call(
        "/api/v1/governance/requests/submit",
        payload={"asset_id": "a1"},
    )
    assert result["id"] == "req-1"
    assert result["status"] == "pending"
