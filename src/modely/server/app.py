"""Server application factory for the dependency-light enterprise API skeleton.

Phase 1b wires the full P0/P1 route set into a thin registry.  Routes accept
injected services and return envelope-wrapped payloads; they delegate business
logic to ``application/``, ``cataloging/``, ``syncing/``, and ``storage/``.

Example usage (local smoke test)::

    from modely.cataloging.repository import InMemoryLocalMirrorRepository
    from modely.server.app import create_app

    repository = InMemoryLocalMirrorRepository()
    app = create_app(repository=repository)
    result = app.call("/api/v1/assets", request_id="req_test")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .routes.health import get_health, get_version
from .routes.catalog import get_asset, get_asset_download_url, get_asset_file_preview, get_asset_files, list_assets
from .routes.governance import (
    approve_request,
    cancel_request,
    evaluate_policy,
    get_request,
    list_requests,
    reject_request,
    submit_approval,
)
from .routes.admin import (
    delete_quota,
    get_credential,
    get_quota,
    list_audit_events_admin,
    list_credentials,
    list_quotas,
    register_credential,
    revoke_credential,
    set_quota,
)
from .routes.reports import create_report
from .routes.intelligence import (
    admission_score_route,
    alternatives_route,
    asset_graph_route,
    compliance_report_route,
    cost_recommendations_route,
    lifecycle_route,
    recommendations_route,
    risk_trends_route,
    search_route,
    usage_route,
)
from .routes.reproducibility import (
    create_snapshot_route,
    diff_manifests_route,
    evaluate_ci_gate_route,
    get_snapshot_route,
    list_snapshots_route,
    promote_snapshot_route,
    record_usage_event_route,
    resolve_approved_route,
    rollback_snapshot_route,
    snapshot_history_route,
    validate_lockfile,
)
from .routes.sync import create_sync_job, get_sync_job, get_sync_job_logs
from .routes.watch import add_watch_target, check_drift, get_watch_history, list_watch_targets, remote_search_route, remove_watch_target
from .routes.service_accounts import (
    create_service_account,
    create_token_for_sa,
    get_service_account,
    list_service_accounts,
)

RouteHandler = Callable[..., dict[str, Any]]


@dataclass
class ModelyServerApp:
    """Tiny framework-neutral route registry used until FastAPI is selected.

    Each route handler receives optional ``request_id`` and ``service``
    keyword arguments when called through the app.
    """

    routes: dict[str, RouteHandler] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)

    def route(self, path: str, handler: RouteHandler) -> None:
        self.routes[path] = handler

    def call(self, path: str, **kwargs) -> dict[str, Any]:
        """Route a request by path, injecting app-scoped services automatically."""
        if path not in self.routes:
            raise KeyError(f"Unknown route: {path}")
        handler = self.routes[path]
        # Inject services when the caller hasn't provided them explicitly
        for svc_name in ("service", "auth_service", "repository", "storage"):
            if svc_name not in kwargs and svc_name in self.services:
                kwargs[svc_name] = self.services[svc_name]
        return handler(**kwargs)


def create_app(
    *,
    repository: Any = None,
    storage: Any = None,
    catalog_service: Any = None,
    sync_service: Any = None,
    auth_service: Any = None,
) -> ModelyServerApp:
    """Create a minimal app registry without adding heavy server dependencies to core.

    Accepts optional service dependencies.  When not provided, routes that
    require them will error if called without an explicit per-call ``service=`` kwarg.
    """

    app = ModelyServerApp()

    # -- shared services -----------------------------------------------------------
    if catalog_service is not None:
        app.services["catalog_service"] = catalog_service
        app.services["service"] = catalog_service  # default "service" used by older routes
    if sync_service is not None:
        app.services["sync_service"] = sync_service
    if auth_service is not None:
        app.services["auth_service"] = auth_service
    if repository is not None:
        app.services["repository"] = repository
    if storage is not None:
        app.services["storage"] = storage

    # -- P0 health / version -------------------------------------------------------
    app.route("/api/v1/health", get_health)
    app.route("/api/v1/version", get_version)

    # -- P0 catalog ----------------------------------------------------------------
    app.route("/api/v1/assets", list_assets)
    app.route("/api/v1/assets/{id}", get_asset)

    # -- P1 catalog diagnostics ----------------------------------------------------
    app.route("/api/v1/assets/{id}/files", get_asset_files)
    app.route("/api/v1/assets/{id}/files/preview", get_asset_file_preview)
    app.route("/api/v1/assets/{id}/download-url", get_asset_download_url)

    # -- P0 sync -------------------------------------------------------------------
    app.route("/api/v1/sync-jobs", create_sync_job)   # handles GET + POST via _method
    app.route("/api/v1/sync-jobs/{id}", get_sync_job)

    # -- P1 sync diagnostics -------------------------------------------------------
    app.route("/api/v1/sync-jobs/{id}/logs", get_sync_job_logs)

    # -- Watch / monitoring --------------------------------------------------------
    app.route("/api/v1/watch/targets", list_watch_targets)
    app.route("/api/v1/watch/targets/add", add_watch_target)
    app.route("/api/v1/watch/targets/remove", remove_watch_target)
    app.route("/api/v1/watch/check", check_drift)
    app.route("/api/v1/watch/history", get_watch_history)
    app.route("/api/v1/watch/discover", remote_search_route)

    # -- Phase 3a lockfile validation ---------------------------------------------
    app.route("/api/v1/lockfiles/validate", validate_lockfile)

    # -- Phase 3a manifest diff ---------------------------------------------------
    app.route("/api/v1/manifests/diff", diff_manifests_route)

    # -- Phase 3a snapshots -------------------------------------------------------
    app.route("/api/v1/snapshots", list_snapshots_route)  # GET list
    app.route("/api/v1/snapshots/create", create_snapshot_route)  # POST create
    app.route("/api/v1/snapshots/{id}", get_snapshot_route)
    app.route("/api/v1/snapshots/promote", promote_snapshot_route)
    app.route("/api/v1/snapshots/{id}/rollback", rollback_snapshot_route)
    app.route("/api/v1/snapshots/{id}/history", snapshot_history_route)

    # -- Phase 3b CI gate ---------------------------------------------------------
    app.route("/api/v1/ci-gates/evaluate", evaluate_ci_gate_route)

    # -- Phase 3c platform handoff -------------------------------------------------
    app.route("/api/v1/assets/{id}/resolve-approved", resolve_approved_route)
    app.route("/api/v1/platform-usage-events", record_usage_event_route)

    # -- Phase 4a search & analytics ----------------------------------------------
    app.route("/api/v1/search", search_route)
    app.route("/api/v1/analytics/risk", risk_trends_route)
    app.route("/api/v1/analytics/usage", usage_route)

    # -- Phase 4b recommendations & scoring --------------------------------------
    app.route("/api/v1/assets/{id}/recommendations", recommendations_route)
    app.route("/api/v1/assets/{id}/alternatives", alternatives_route)
    app.route("/api/v1/assets/{id}/admission-score", admission_score_route)

    # -- Phase 4c graph, compliance, lifecycle, cost ------------------------------
    app.route("/api/v1/graph/assets/{id}", asset_graph_route)
    app.route("/api/v1/reports/compliance", compliance_report_route)
    app.route("/api/v1/analytics/lifecycle", lifecycle_route)
    app.route("/api/v1/analytics/cost/recommendations", cost_recommendations_route)

    # -- Phase 2 governance -------------------------------------------------------
    app.route("/api/v1/governance/policy/evaluate", evaluate_policy)
    app.route("/api/v1/governance/requests", list_requests)
    app.route("/api/v1/governance/requests/submit", submit_approval)
    app.route("/api/v1/governance/requests/{id}", get_request)
    app.route("/api/v1/governance/requests/{id}/approve", approve_request)
    app.route("/api/v1/governance/requests/{id}/reject", reject_request)
    app.route("/api/v1/governance/requests/{id}/cancel", cancel_request)

    # -- Phase 2 admin ------------------------------------------------------------
    app.route("/api/v1/admin/quotas", list_quotas)
    app.route("/api/v1/admin/quotas/set", set_quota)
    app.route("/api/v1/admin/quotas/{id}", get_quota)
    app.route("/api/v1/admin/quotas/{id}/delete", delete_quota)
    app.route("/api/v1/admin/credentials", list_credentials)
    app.route("/api/v1/admin/credentials/{id}", get_credential)
    app.route("/api/v1/admin/credentials/register", register_credential)
    app.route("/api/v1/admin/credentials/{id}/revoke", revoke_credential)
    app.route("/api/v1/admin/audit", list_audit_events_admin)

    # -- Service accounts & tokens (dev/demo stubs) -------------------------------
    app.route("/api/v1/service-accounts", list_service_accounts)
    app.route("/api/v1/service-accounts/create", create_service_account)
    app.route("/api/v1/service-accounts/{id}", get_service_account)
    app.route("/api/v1/service-accounts/{id}/tokens", create_token_for_sa)

    # -- Phase 2 governance reports -----------------------------------------------
    app.route("/api/v1/reports/governance", create_report)

    return app


__all__ = ["ModelyServerApp", "RouteHandler", "create_app", "create_fastapi_app"]


def create_fastapi_app(
    *,
    repository: Any = None,
    storage: Any = None,
    catalog_service: Any = None,
    sync_service: Any = None,
    auth_service: Any = None,
) -> "FastAPI":
    """Create a FastAPI application wired to the ``ModelyServerApp`` route registry.

    FastAPI is an optional dependency (``modely-ai[server]``).  Each registered
    modely route is exposed as a FastAPI endpoint that delegates to the in-process
    ``ModelyServerApp`` handler, preserving the service-injection and
    envelope-wrapping contracts.

    Example::

        pip install modely-ai[server]
        python -m modely.server
    """
    from fastapi import FastAPI

    modely = create_app(
        repository=repository,
        storage=storage,
        catalog_service=catalog_service,
        sync_service=sync_service,
        auth_service=auth_service,
    )

    fastapi_app = FastAPI(
        title="modely-server",
        version="0.1.0",
        description="Enterprise AI asset governance API",
    )

    # Map modely routes to FastAPI endpoints
    _register_routes(fastapi_app, modely)

    return fastapi_app


def _register_routes(fastapi_app: Any, modely: ModelyServerApp) -> None:
    """Register every route in *modely* as a FastAPI endpoint.

    Each route is registered directly on the FastAPI app.  Handler arguments
    are resolved from: path params, query params, request body, and
    modely services (only injected when the handler expects them).
    """
    import inspect

    from fastapi import Request

    def _make_handler(path: str, handler: Any):
        sig = inspect.signature(handler)
        known_params = set(sig.parameters.keys())

        async def endpoint(request: Request) -> dict:
            kwargs: dict[str, Any] = {}

            # Pass request method so handlers can distinguish GET vs POST
            if "_method" in known_params or "**kwargs" in str(sig):
                kwargs["_method"] = request.method

            # Path parameters (e.g. /api/v1/assets/{id})
            pp = dict(getattr(request, "path_params", {}) or {})
            # Map {id} → asset_id / job_id when the handler expects them
            if "id" in pp and "id" not in known_params:
                for target in ("asset_id", "job_id"):
                    if target in known_params:
                        pp[target] = pp.pop("id")
                        break
            kwargs.update(pp)

            # Query parameters — passed both as unpacked **kwargs (so
            # handlers that use ``**query_params`` receive them directly),
            # and also merged into ``payload`` for handlers that expect that
            # convention.
            qp = dict(request.query_params)
            if qp:
                # Unpack into kwargs so ``**query_params`` handlers see them
                kwargs.update(qp)
                # Only inject ``payload`` when the handler expects it
                if "payload" in known_params or "**kwargs" in str(sig):
                    if isinstance(kwargs.get("payload"), dict):
                        kwargs["payload"].update(qp)
                    else:
                        kwargs["payload"] = dict(qp)

            # Request body for POST/PUT
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body = await request.json()
                    if isinstance(body, dict):
                        # Unpack into kwargs so named params (e.g. ``config=``)
                        # can be matched directly.
                        kwargs.update(body)
                        if isinstance(kwargs.get("payload"), dict):
                            kwargs["payload"].update(body)
                        else:
                            kwargs["payload"] = body
                except Exception:
                    pass

            # Inject services only when the handler expects them
            for svc_name in modely.services:
                if svc_name in known_params and svc_name not in kwargs:
                    kwargs[svc_name] = modely.services[svc_name]

            return handler(**kwargs)

        endpoint.__annotations__ = {"request": Request, "return": dict}
        return endpoint

    for path, handler in modely.routes.items():
        methods = _methods_for_path(path)
        ep = _make_handler(path, handler)

        for method in methods:
            if method == "GET":
                fastapi_app.get(path)(ep)
            elif method == "POST":
                fastapi_app.post(path)(ep)
            elif method == "DELETE":
                fastapi_app.delete(path)(ep)


def _methods_for_path(path: str) -> list[str]:
    """Guess the HTTP method(s) from the route path convention."""
    if any(verb in path for verb in ("/submit", "/create", "/register", "/set", "/evaluate", "/check", "/add", "/remove")):
        return ["POST"]
    if any(verb in path for verb in ("/approve", "/reject", "/cancel", "/revoke")):
        return ["POST"]
    if "/delete" in path:
        return ["DELETE"]
    # Routes that support both listing (GET) + creation (POST)
    if path in ("/api/v1/sync-jobs", "/api/v1/service-accounts"):
        return ["GET", "POST"]
    return ["GET"]
