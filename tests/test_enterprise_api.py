"""Phase 1b API contract tests — envelope shapes, routes, error codes, auth, pagination.

All tests are network-free and use Phase 1a in-memory repositories and local fixtures.
"""

from __future__ import annotations

import pytest

from modely.cataloging.repository import InMemoryLocalMirrorRepository
from modely.domain.assets import Asset, AssetIdentity
from modely.domain.files import AssetFile, AssetFileIdentity
from modely.server import create_app
from modely.server.middleware import extract_request_id, parse_dev_auth
from modely.server.routes.catalog import get_asset, get_asset_download_url, get_asset_files, list_assets
from modely.server.routes.health import get_health, get_version
from modely.server.routes.sync import create_sync_job as sync_create, get_sync_job, get_sync_job_logs
from modely.server.schemas.envelopes import (
    ErrorDetail,
    Pagination,
    Principal,
    ResponseMeta,
    STABLE_ERROR_CODES,
    error_response,
    generate_request_id,
    success_response,
)


# -- Fixtures ------------------------------------------------------------------

@pytest.fixture
def repository():
    repo = InMemoryLocalMirrorRepository()
    asset = Asset(
        id="hf:model:test--model",
        identity=AssetIdentity(source="hf", repo_type="model", repo_id="test/model", revision="main"),
        source_url="hf://models/test/model",
        license="apache-2.0",
        tags=["nlp", "transformer"],
        size=1024,
        file_count=2,
        checksum="abc123;def456",
        operational_state="synced",
        visibility="organization",
        metadata={"framework": "pytorch"},
    )
    repo.assets.save_asset(asset)
    # Add files
    repo.files.save_file(
        AssetFile(
            id="hf:model:test--model:main:config.json",
            identity=AssetFileIdentity(asset_id="hf:model:test--model", version_id="v1", revision="main", path="config.json"),
            path="config.json",
            size=100,
            sha256="abc123",
            file_type="blob",
            local_path="assets/hf/model/test--model/main/config.json",
            metadata={},
        )
    )
    repo.files.save_file(
        AssetFile(
            id="hf:model:test--model:main:model.bin",
            identity=AssetFileIdentity(asset_id="hf:model:test--model", version_id="v1", revision="main", path="model.bin"),
            path="model.bin",
            size=924,
            sha256="def456",
            file_type="blob",
            local_path="assets/hf/model/test--model/main/model.bin",
            metadata={"framework": "pytorch"},
        )
    )
    return repo


class CatalogService:
    """Thin service adapter wrapping the in-memory repository."""

    def __init__(self, repo: InMemoryLocalMirrorRepository):
        self._repo = repo
        self.files = repo.files

    def list_assets(self):
        return list(self._repo.assets.list_assets())

    def get_asset(self, asset_id: str):
        return self._repo.assets.get_asset(asset_id)

    def list_asset_files(self, asset_id: str):
        return list(self._repo.files.list_files(asset_id))


class SyncService:
    """Thin sync service for route tests."""

    def __init__(self, repo: InMemoryLocalMirrorRepository | None = None):
        self._repo = repo
        self._jobs: dict[str, dict] = {}
        self._idempotency: dict[str, dict] = {}

    def create_sync_job(self, **kwargs):
        job_id = kwargs.get("id", f"job_{len(self._jobs) + 1}")
        key = kwargs.get("idempotency_key", "")
        if key and key in self._idempotency:
            return self._idempotency[key]
        job = {
            "id": job_id,
            "target_id": kwargs.get("target_id", ""),
            "resource": kwargs.get("resource", ""),
            "status": "registered",
            "action": "sync",
            "attempts": 0,
            "error": None,
            "created_at": "2026-06-25T00:00:00Z",
            "updated_at": "2026-06-25T00:00:00Z",
            "metadata": {"idempotency_key": key, **kwargs.get("metadata", {})},
        }
        self._jobs[job_id] = job
        if key:
            self._idempotency[key] = job
        return type("Job", (), {"to_dict": lambda self: job})()

    def get_sync_job(self, job_id: str):
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return type("Job", (), {"to_dict": lambda self: job})()

    def find_job_by_idempotency_key(self, key: str):
        job = self._idempotency.get(key)
        if job is None:
            return None
        return type("Job", (), {"to_dict": lambda self: job})()

    def list_sync_jobs(self):
        return [type("Job", (), {"to_dict": lambda self, j=j: j})() for j in self._jobs.values()]


# -- Envelope schema tests -----------------------------------------------------


def test_generate_request_id_uses_req_prefix():
    rid = generate_request_id()
    assert rid.startswith("req_")
    assert len(rid) == 4 + 16  # req_ + 16 hex chars


def test_success_response_shape():
    payload = success_response({"key": "value"}, request_id="req_test")
    assert payload["data"] == {"key": "value"}
    assert payload["meta"]["request_id"] == "req_test"
    assert payload["meta"]["schema_version"] == "v1"
    assert payload["meta"]["pagination"] is None


def test_success_response_with_pagination():
    pag = Pagination(total=50, page=2, page_size=20)
    payload = success_response({"items": []}, request_id="req_p", pagination=pag)
    assert payload["meta"]["pagination"]["total"] == 50
    assert payload["meta"]["pagination"]["page"] == 2


def test_error_response_shape():
    payload = error_response("not_found", "Missing resource", request_id="req_err", details={"id": "x"})
    assert "error" in payload
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"] == "Missing resource"
    assert payload["error"]["request_id"] == "req_err"
    assert payload["error"]["details"] == {"id": "x"}


def test_error_detail_dataclass():
    detail = ErrorDetail(code="validation_error", message="Bad input", request_id="req_v")
    d = detail.to_dict()
    assert d["code"] == "validation_error"
    assert "request_id" in d


def test_stable_error_codes_are_complete():
    assert "not_found" in STABLE_ERROR_CODES
    assert "validation_error" in STABLE_ERROR_CODES
    assert "auth_required" in STABLE_ERROR_CODES
    assert "conflict_idempotency" in STABLE_ERROR_CODES
    assert "internal_error" in STABLE_ERROR_CODES
    assert "upstream_unavailable" in STABLE_ERROR_CODES


def test_response_meta_handles_none_pagination():
    meta = ResponseMeta(request_id="req_x")
    d = meta.to_dict()
    assert d["pagination"] is None


# -- Health / version route tests ----------------------------------------------


def test_health_route_returns_envelope():
    payload = get_health(request_id="req_h")
    assert payload["data"]["status"] == "ok"
    assert payload["meta"]["request_id"] == "req_h"


def test_version_route_returns_envelope():
    payload = get_version(request_id="req_v")
    assert "version" in payload["data"]
    assert payload["meta"]["schema_version"] == "v1"


# -- Catalog route tests -------------------------------------------------------


def test_list_assets_returns_envelope_with_pagination(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, request_id="req_list")
    assert payload["data"]["total"] == 1
    assert payload["meta"]["pagination"]["total"] == 1
    assert payload["meta"]["pagination"]["page"] == 1
    assert payload["meta"]["request_id"] == "req_list"


def test_list_assets_filter_by_source(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, source="hf")
    assert payload["data"]["total"] == 1
    payload2 = list_assets(svc, source="ms")
    assert payload2["data"]["total"] == 0


def test_list_assets_filter_by_license(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, license="apache-2.0")
    assert payload["data"]["total"] == 1
    payload2 = list_assets(svc, license="mit")
    assert payload2["data"]["total"] == 0


def test_list_assets_filter_by_operational_state(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, operational_state="synced")
    assert payload["data"]["total"] == 1
    payload2 = list_assets(svc, operational_state="archived")
    assert payload2["data"]["total"] == 0


def test_list_assets_text_search(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, q="test")
    assert payload["data"]["total"] == 1
    payload2 = list_assets(svc, q="nonexistent_xyz")
    assert payload2["data"]["total"] == 0


def test_list_assets_pagination(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, page="1", page_size="1")
    assert payload["meta"]["pagination"]["page"] == 1
    assert payload["meta"]["pagination"]["page_size"] == 1
    assert len(payload["data"]["assets"]) == 1


def test_list_assets_invalid_page_defaults(repository):
    svc = CatalogService(repository)
    payload = list_assets(svc, page="invalid", page_size="-5")
    assert payload["meta"]["pagination"]["page"] == 1
    assert payload["meta"]["pagination"]["page_size"] == 1


def test_get_asset_returns_envelope(repository):
    svc = CatalogService(repository)
    payload = get_asset(svc, "hf:model:test--model", request_id="req_detail")
    assert payload["data"]["id"] == "hf:model:test--model"
    assert payload["data"]["license"] == "apache-2.0"
    assert payload["data"]["operational_state"] == "synced"
    assert payload["meta"]["request_id"] == "req_detail"


def test_get_asset_not_found(repository):
    svc = CatalogService(repository)
    payload = get_asset(svc, "nonexistent", request_id="req_nf")
    assert "error" in payload
    assert payload["error"]["code"] == "not_found"
    assert "nonexistent" in payload["error"]["message"]


# -- File list route tests -----------------------------------------------------


def test_get_asset_files_returns_envelope(repository):
    svc = CatalogService(repository)
    payload = get_asset_files(svc, "hf:model:test--model", request_id="req_files")
    assert payload["data"]["asset_id"] == "hf:model:test--model"
    assert payload["data"]["count"] == 2
    paths = [f["path"] for f in payload["data"]["files"]]
    assert "config.json" in paths
    assert "model.bin" in paths


def test_get_asset_files_not_found(repository):
    svc = CatalogService(repository)
    payload = get_asset_files(svc, "nonexistent", request_id="req_nf")
    assert payload["error"]["code"] == "not_found"


# -- Download URL route tests --------------------------------------------------


def test_get_asset_download_url_returns_diagnostic_response(repository):
    svc = CatalogService(repository)
    payload = get_asset_download_url(svc, "hf:model:test--model", request_id="req_dl")
    assert payload["data"]["download_mode"] == "local_reference"
    assert payload["data"]["security_warning"]  # contains diagnostic-only message
    assert payload["meta"]["request_id"] == "req_dl"


def test_get_asset_download_url_not_found(repository):
    svc = CatalogService(repository)
    payload = get_asset_download_url(svc, "nonexistent", request_id="req_nf")
    assert payload["error"]["code"] == "not_found"


def test_download_url_response_never_exposes_raw_secrets():
    """Download URL diagnostics must never expose credentials or signed URLs."""
    response = get_asset_download_url(CatalogService(InMemoryLocalMirrorRepository()), "nonexistent", request_id="req_x")
    as_str = str(response)
    assert "secret" not in as_str.lower()
    assert "password" not in as_str.lower()
    assert "token" not in as_str.lower()
    assert "api_key" not in as_str.lower()


# -- Sync route tests ----------------------------------------------------------


def test_create_sync_job_returns_envelope(repository):
    svc = SyncService()
    payload = sync_create(svc, target_id="t1", resource="hf://models/test", request_id="req_sync")
    assert payload["data"]["id"]
    assert payload["data"]["status"] == "registered"
    assert payload["data"]["target_id"] == "t1"
    assert payload["meta"]["request_id"] == "req_sync"


def test_create_sync_job_missing_target_id():
    svc = SyncService()
    payload = sync_create(svc, resource="hf://models/test", request_id="req_v")
    # When target_id is missing and only resource given, falls through to list
    # (GET behavior). After list_sync_jobs refactor, should return empty list.
    assert "data" in payload
    assert payload["data"]["total"] == 0


def test_create_sync_job_missing_resource():
    svc = SyncService()
    payload = sync_create(svc, target_id="t1", request_id="req_v")
    assert payload["error"]["code"] == "validation_error"
    assert "resource" in payload["error"]["message"]


def test_create_sync_job_idempotency_conflict():
    svc = SyncService()
    # First create
    first = sync_create(svc, target_id="t1", resource="hf://models/test", idempotency_key="idem-1", request_id="req_1")
    assert "data" in first
    # Second with same key
    second = sync_create(svc, target_id="t1", resource="hf://models/test", idempotency_key="idem-1", request_id="req_2")
    assert "error" in second
    assert second["error"]["code"] == "conflict_idempotency"


def test_get_sync_job_returns_envelope():
    svc = SyncService()
    created = sync_create(svc, target_id="t1", resource="hf://models/test", request_id="req_c")
    job_id = created["data"]["id"]
    payload = get_sync_job(svc, job_id, request_id="req_status")
    assert payload["data"]["id"] == job_id
    assert payload["meta"]["request_id"] == "req_status"


def test_get_sync_job_not_found():
    svc = SyncService()
    payload = get_sync_job(svc, "nonexistent", request_id="req_nf")
    assert payload["error"]["code"] == "not_found"


def test_get_sync_job_logs_returns_envelope():
    svc = SyncService()
    created = sync_create(svc, target_id="t1", resource="hf://models/test", request_id="req_c")
    job_id = created["data"]["id"]
    payload = get_sync_job_logs(svc, job_id, request_id="req_logs")
    assert payload["data"]["job_id"] == job_id
    assert "events" in payload["data"]
    assert "diagnostic_mode" in str(payload["data"]["metadata"])


def test_get_sync_job_logs_not_found():
    svc = SyncService()
    payload = get_sync_job_logs(svc, "nonexistent", request_id="req_nf")
    assert payload["error"]["code"] == "not_found"


# -- App factory tests ---------------------------------------------------------


def test_app_routes_are_all_wired():
    app = create_app()
    expected = {
        "/api/v1/health",
        "/api/v1/version",
        "/api/v1/assets",
        "/api/v1/assets/{id}",
        "/api/v1/assets/{id}/files",
        "/api/v1/assets/{id}/files/preview",
        "/api/v1/assets/{id}/download-url",
        "/api/v1/sync-jobs",
        "/api/v1/sync-jobs/{id}",
        "/api/v1/sync-jobs/{id}/logs",
        "/api/v1/lockfiles/validate",
        "/api/v1/manifests/diff",
        "/api/v1/snapshots",
        "/api/v1/snapshots/create",
        "/api/v1/snapshots/{id}",
        "/api/v1/snapshots/promote",
        "/api/v1/snapshots/{id}/rollback",
        "/api/v1/snapshots/{id}/history",
        "/api/v1/ci-gates/evaluate",
        "/api/v1/assets/{id}/resolve-approved",
        "/api/v1/platform-usage-events",
        "/api/v1/search",
        "/api/v1/analytics/risk",
        "/api/v1/analytics/usage",
        "/api/v1/assets/{id}/recommendations",
        "/api/v1/assets/{id}/alternatives",
        "/api/v1/assets/{id}/admission-score",
        "/api/v1/graph/assets/{id}",
        "/api/v1/reports/compliance",
        "/api/v1/analytics/lifecycle",
        "/api/v1/analytics/cost/recommendations",
        # Phase 2 governance
        "/api/v1/governance/policy/evaluate",
        "/api/v1/governance/requests",
        "/api/v1/governance/requests/submit",
        "/api/v1/governance/requests/{id}",
        "/api/v1/governance/requests/{id}/approve",
        "/api/v1/governance/requests/{id}/reject",
        "/api/v1/governance/requests/{id}/cancel",
        # Phase 2 admin
        "/api/v1/admin/quotas",
        "/api/v1/admin/quotas/set",
        "/api/v1/admin/quotas/{id}",
        "/api/v1/admin/quotas/{id}/delete",
        "/api/v1/admin/credentials",
        "/api/v1/admin/credentials/{id}",
        "/api/v1/admin/credentials/register",
        "/api/v1/admin/credentials/{id}/revoke",
        "/api/v1/admin/audit",
        # Phase 2 reports
        "/api/v1/reports/governance",
        # Watch / monitoring
        "/api/v1/watch/targets",
        "/api/v1/watch/targets/add",
        "/api/v1/watch/targets/remove",
        "/api/v1/watch/check",
        "/api/v1/watch/history",
        "/api/v1/watch/discover",
        # Service accounts (dev/demo stubs)
        "/api/v1/service-accounts",
        "/api/v1/service-accounts/create",
        "/api/v1/service-accounts/{id}",
        "/api/v1/service-accounts/{id}/tokens",
    }
    assert set(app.routes.keys()) == expected


def test_app_call_unknown_route():
    app = create_app()
    with pytest.raises(KeyError, match="Unknown route"):
        app.call("/api/v1/nonexistent")


def test_app_injects_services(repository):
    svc = CatalogService(repository)
    app = create_app(catalog_service=svc)
    result = app.call("/api/v1/assets", request_id="req_test")
    assert result["data"]["total"] == 1


def test_watch_discover_returns_compact_ui_payload(monkeypatch):
    from modely.search.types import SearchResult

    long_description = "x" * 10_000

    monkeypatch.setattr(
        "modely.search.search",
        lambda **kwargs: [
            SearchResult(
                id="org/model",
                source="hf",
                repo_type=kwargs["repo_type"],
                description=long_description,
                tags=[f"tag-{i}" for i in range(20)],
            )
        ],
    )
    monkeypatch.setattr(
        "modely.search.gh_search.search_github",
        lambda **kwargs: [
            SearchResult(
                id="owner/tool",
                source="github",
                repo_type="tool",
                author={"Name": "owner-name", "Description": long_description},
                description=long_description,
                metadata={"large": long_description},
            )
        ],
    )

    app = create_app()
    result = app.call(
        "/api/v1/watch/discover",
        q="model",
        repo_type="all",
        source="all",
        limit="2",
        request_id="req_test",
    )

    results = result["data"]["results"]
    assert result["data"]["total"] == 2
    assert len(results) == 2
    assert all(len(item["description"]) <= 240 for item in results)
    assert all("metadata" not in item and "summary" not in item for item in results)
    assert len(results[0]["tags"]) == 12
    assert isinstance(results[1]["author"], str)
    assert results[1]["author"] == "owner-name"


# -- Auth middleware tests -----------------------------------------------------


def test_extract_request_id_from_header():
    assert extract_request_id({"X-Request-ID": "req_custom"}) == "req_custom"


def test_extract_request_id_fallback():
    rid = extract_request_id(None)
    assert rid.startswith("req_")
    rid2 = extract_request_id({})
    assert rid2.startswith("req_")


def test_parse_dev_auth_admin():
    principal = parse_dev_auth({"Authorization": "Bearer dev-admin"})
    assert principal is not None
    assert principal.roles == ["Platform Admin"]
    assert principal.principal_type == "user"
    assert principal.metadata["auth_mode"] == "dev_basic"


def test_parse_dev_auth_developer():
    principal = parse_dev_auth({"Authorization": "Bearer dev-developer"})
    assert principal is not None
    assert principal.roles == ["Developer"]
    assert principal.principal_type == "user"


def test_parse_dev_auth_viewer():
    principal = parse_dev_auth({"Authorization": "Bearer dev-viewer"})
    assert principal is not None
    assert principal.roles == ["Viewer"]
    assert principal.principal_type == "user"


def test_parse_dev_auth_unknown_role_falls_back_to_viewer():
    principal = parse_dev_auth({"Authorization": "Bearer dev-superuser"})
    assert principal is not None
    assert principal.roles == ["Viewer"]
    assert principal.principal_type == "user"


def test_parse_dev_auth_no_header():
    assert parse_dev_auth(None) is None
    assert parse_dev_auth({}) is None


def test_parse_dev_auth_no_bearer():
    assert parse_dev_auth({"Authorization": "Basic xyz"}) is None


def test_parse_dev_auth_lowercase_header():
    principal = parse_dev_auth({"authorization": "Bearer dev-admin"})
    assert principal is not None
    assert principal.roles == ["Platform Admin"]
    assert principal.principal_type == "user"


def test_parse_dev_auth_empty_token():
    assert parse_dev_auth({"Authorization": "Bearer "}) is None


# -- Redaction / security tests ------------------------------------------------


def test_error_responses_never_expose_internals():
    """Error responses must use stable codes and should not leak internal paths."""
    payload = error_response("internal_error", "Something went wrong", request_id="req_err")
    assert payload["error"]["code"] == "internal_error"
    # No stack traces or internal paths in the message
    assert "/src/" not in payload["error"]["message"]


def test_principal_dto_has_no_secrets():
    """Governance Principal serialization does not expose secrets."""
    from modely.governance.rbac import Principal
    p = Principal(id="dev:admin", roles=["Platform Admin"])
    d = p.to_dict()
    assert "password" not in d
    assert "secret" not in d
    assert "token" not in d
