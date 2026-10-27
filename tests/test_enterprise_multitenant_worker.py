"""Tests for multi-tenant isolation (#5) and worker queue abstraction (#4)."""

from __future__ import annotations

import pytest

from modely.cataloging.repository import InMemoryLocalMirrorRepository
from modely.domain.assets import Asset, AssetIdentity
from modely.domain.tenants import TenantScope
from modely.governance.tenant_isolation import (
    TenantContext,
    TenantFilteredRepository,
    _asset_matches_tenant,
)
from modely.application.worker_queue import (
    InProcessTaskQueue,
    enqueue_sync_job,
    enqueue_scan_job,
    enqueue_report_job,
)


# -- Multi-tenant isolation tests (5) ------------------------------------------


def test_asset_matches_same_tenant():
    scope = TenantScope(organization_id="org-1", workspace_id="ws-1")
    asset = Asset(id="a1", identity=AssetIdentity(source="hf", repo_type="model"))
    asset.tenant_scope = scope
    assert _asset_matches_tenant(asset, scope) is True


def test_asset_matches_different_org():
    scope1 = TenantScope(organization_id="org-1", workspace_id="ws-1")
    scope2 = TenantScope(organization_id="org-2", workspace_id="ws-1")
    asset = Asset(id="a1", identity=AssetIdentity(source="hf", repo_type="model"))
    asset.tenant_scope = scope1
    assert _asset_matches_tenant(asset, scope2) is False


def test_asset_without_tenant_visible_to_all():
    scope = TenantScope(organization_id="org-1", workspace_id="ws-1")
    asset = Asset(id="a1", identity=AssetIdentity(source="hf", repo_type="model"))
    assert _asset_matches_tenant(asset, scope) is True


def test_tenant_filtered_repository_lists_only_matching():
    repo = InMemoryLocalMirrorRepository()
    scope1 = TenantScope(organization_id="org-1", workspace_id="ws-1")
    scope2 = TenantScope(organization_id="org-2", workspace_id="ws-2")

    a1 = Asset(id="a1", identity=AssetIdentity(source="hf", repo_type="model"))
    a1.tenant_scope = scope1
    repo.assets.save_asset(a1)

    a2 = Asset(id="a2", identity=AssetIdentity(source="hf", repo_type="model"))
    a2.tenant_scope = scope2
    repo.assets.save_asset(a2)

    ctx = TenantContext(tenant_scope=scope1)
    filtered = TenantFilteredRepository(repo, ctx)

    assets = filtered.assets.list_assets()
    assert len(assets) == 1
    assert assets[0].id == "a1"


def test_tenant_filtered_get_returns_none_for_wrong_tenant():
    repo = InMemoryLocalMirrorRepository()
    scope1 = TenantScope(organization_id="org-1", workspace_id="ws-1")
    scope2 = TenantScope(organization_id="org-2", workspace_id="ws-2")

    a1 = Asset(id="a1", identity=AssetIdentity(source="hf", repo_type="model"))
    a1.tenant_scope = scope1
    repo.assets.save_asset(a1)

    ctx = TenantContext(tenant_scope=scope2)
    filtered = TenantFilteredRepository(repo, ctx)

    assert filtered.assets.get_asset("a1") is None


def test_tenant_filtered_save_sets_scope():
    repo = InMemoryLocalMirrorRepository()
    scope = TenantScope(organization_id="org-1", workspace_id="ws-1")
    ctx = TenantContext(tenant_scope=scope)
    filtered = TenantFilteredRepository(repo, ctx)

    a1 = Asset(id="a1", identity=AssetIdentity(source="hf", repo_type="model"))
    filtered.assets.save_asset(a1)

    saved = repo.assets.get_asset("a1")
    assert saved.tenant_scope.organization_id == "org-1"


def test_tenant_context_default():
    ctx = TenantContext.default_org("my-org", "my-ws")
    assert ctx.tenant_scope.organization_id == "my-org"
    assert ctx.principal_id == ""


# -- Worker queue tests (4) ----------------------------------------------------


def test_in_process_queue_enqueue_and_result():
    q = InProcessTaskQueue()
    task_id = q.enqueue(lambda x: x * 2, 21)
    result = q.get_result(task_id)
    assert result["status"] == "completed"
    assert result["result"] == 42


def test_enqueue_sync_job():
    from modely.syncing.jobs import create_sync_job
    from modely.syncing.workers import LocalMirrorWorker
    from modely.syncing.adapters import FixtureSourceAdapter
    from modely.storage.local import LocalStorageBackend
    import tempfile, os

    tmp = tempfile.mkdtemp()
    root = os.path.join(tmp, "fixture")
    os.makedirs(root)
    with open(os.path.join(root, "config.json"), "w") as f:
        f.write("{}")

    job = create_sync_job("j1", target_id="t1", resource="hf://models/test/model", revision="main")
    worker = LocalMirrorWorker(
        adapter=FixtureSourceAdapter(root),
        storage=LocalStorageBackend(os.path.join(tmp, "store")),
    )
    q = InProcessTaskQueue()
    task_id = enqueue_sync_job(job, queue=q, worker=worker)
    result = q.get_result(task_id)
    assert result is not None
    assert result["status"] == "completed"


def test_enqueue_scan_job():
    q = InProcessTaskQueue()
    task_id = enqueue_scan_job("asset_1", queue=q)
    result = q.get_result(task_id)
    assert result["status"] == "completed"


def test_enqueue_report_job():
    q = InProcessTaskQueue()
    task_id = enqueue_report_job("governance", queue=q, format="json")
    result = q.get_result(task_id)
    assert result["status"] == "completed"


def test_queue_error_handling():
    q = InProcessTaskQueue()

    def failing_task():
        raise ValueError("test error")

    task_id = q.enqueue(failing_task)
    result = q.get_result(task_id)
    assert result["status"] == "failed"
    assert "test error" in result["error"]
