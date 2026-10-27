"""Tests for Phase 3a-3: Approved snapshot model."""

from __future__ import annotations

import pytest

from modely.cataloging.repository import InMemorySnapshotRepository
from modely.domain.snapshots import ApprovedSnapshot, SnapshotChannel
from modely.reproducibility.snapshots import (
    create_snapshot,
    get_snapshot,
    get_snapshot_history,
    list_snapshots,
    promote_snapshot,
    rollback_snapshot,
)
from modely.server.routes.reproducibility import (
    create_snapshot_route,
    get_snapshot_route,
    list_snapshots_route,
    promote_snapshot_route,
    rollback_snapshot_route,
    snapshot_history_route,
)


@pytest.fixture
def repo():
    return InMemorySnapshotRepository()


class SnapshotService:
    def __init__(self, repo: InMemorySnapshotRepository):
        self._repo = repo

    def create_snapshot(self, **kwargs):
        kwargs["repository"] = self._repo
        return create_snapshot(**kwargs)

    def promote_snapshot(self, **kwargs):
        kwargs["repository"] = self._repo
        return promote_snapshot(**kwargs)

    def rollback_snapshot(self, **kwargs):
        kwargs["repository"] = self._repo
        return rollback_snapshot(**kwargs)

    def get_snapshot(self, snapshot_id):
        return get_snapshot(snapshot_id, repository=self._repo)

    def list_snapshots(self, *, asset_id=""):
        return list_snapshots(asset_id, repository=self._repo)

    def get_snapshot_history(self, snapshot_id):
        return get_snapshot_history("asset_1", repository=self._repo)


# -- Snapshot creation tests ---------------------------------------------------


def test_create_snapshot_is_immutable(repo):
    snap = create_snapshot(
        asset_id="asset_1", version_id="v1", manifest_digest="sha256:abc",
        tenant_scope="org1", channel_name="production", created_by="admin",
        repository=repo,
    )
    assert snap.id.startswith("snap_")
    assert snap.asset_id == "asset_1"
    assert snap.tenant_scope == "org1"
    assert snap.channel == "production"

    # Verify immutability
    with pytest.raises(Exception):
        snap.asset_id = "changed"  # frozen dataclass


def test_create_snapshot_creates_channel(repo):
    snap = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="sha256:x", repository=repo)
    channel = repo.get_channel("default", "dev")
    assert channel is not None
    assert channel.current_snapshot_id == snap.id


def test_list_and_get_snapshots(repo):
    snap1 = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="s1", repository=repo)
    snap2 = create_snapshot(asset_id="a1", version_id="v2", manifest_digest="s2", channel_name="staging", repository=repo)

    found = list_snapshots("a1", repository=repo)
    assert len(found) == 2

    got = get_snapshot(snap1.id, repository=repo)
    assert got.manifest_digest == "s1"


# -- Snapshot promotion tests --------------------------------------------------


def test_promote_snapshot_updates_channel(repo):
    snap = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="s1", channel_name="production", repository=repo)

    result = promote_snapshot(snap.id, "production", promoted_by="admin", reason="QA passed", repository=repo)
    assert result.to_snapshot_id == snap.id

    channel = repo.get_channel("default", "production")
    assert channel.current_snapshot_id == snap.id


def test_promote_nonexistent_snapshot(repo):
    with pytest.raises(ValueError, match="Snapshot not found"):
        promote_snapshot("nonexistent", "production", repository=repo)


def test_promote_supersedes_previous(repo):
    snap1 = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="s1", channel_name="production", repository=repo)
    snap2 = create_snapshot(asset_id="a1", version_id="v2", manifest_digest="s2", channel_name="production", repository=repo)

    promote_snapshot(snap1.id, "production", repository=repo)
    promo = promote_snapshot(snap2.id, "production", repository=repo)

    assert promo.from_snapshot_id == snap1.id
    assert promo.to_snapshot_id == snap2.id

    channel = repo.get_channel("default", "production")
    assert channel.current_snapshot_id == snap2.id


# -- Snapshot rollback tests ---------------------------------------------------


def test_rollback_reverts_channel(repo):
    snap1 = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="s1", channel_name="production", repository=repo)
    snap2 = create_snapshot(asset_id="a1", version_id="v2", manifest_digest="s2", channel_name="production", repository=repo)

    promote_snapshot(snap1.id, "production", repository=repo)
    promote_snapshot(snap2.id, "production", repository=repo)

    rollback = rollback_snapshot(snap2.id, "production", reason="bug found", rolled_back_by="admin", repository=repo)
    assert rollback.from_snapshot_id == snap2.id
    assert rollback.to_snapshot_id == snap1.id

    channel = repo.get_channel("default", "production")
    assert channel.current_snapshot_id == snap1.id


def test_rollback_no_prior_snapshot(repo):
    snap = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="s1", channel_name="production", repository=repo)
    with pytest.raises(ValueError, match="No prior snapshot"):
        rollback_snapshot(snap.id, "production", repository=repo)


def test_get_snapshot_history(repo):
    snap1 = create_snapshot(asset_id="a1", version_id="v1", manifest_digest="s1", channel_name="production", repository=repo)
    snap2 = create_snapshot(asset_id="a1", version_id="v2", manifest_digest="s2", channel_name="production", repository=repo)
    promote_snapshot(snap1.id, "production", repository=repo)
    promote_snapshot(snap2.id, "production", repository=repo)

    history = get_snapshot_history("a1", repository=repo)
    assert len(history) >= 2


# -- API route tests -----------------------------------------------------------


def test_create_snapshot_route(repo):
    svc = SnapshotService(repo)
    result = create_snapshot_route(svc, request_id="req_cr", asset_id="asset_1", version_id="v1", manifest_digest="sha256:abc")
    assert result["data"]["asset_id"] == "asset_1"
    assert result["meta"]["request_id"] == "req_cr"


def test_create_snapshot_route_missing_fields(repo):
    svc = SnapshotService(repo)
    result = create_snapshot_route(svc, request_id="req_cr")
    assert result["error"]["code"] == "validation_error"


def test_list_snapshots_route(repo):
    svc = SnapshotService(repo)
    svc.create_snapshot(asset_id="asset_1", version_id="v1", manifest_digest="s1")
    result = list_snapshots_route(svc, request_id="req_list", asset_id="asset_1")
    assert result["data"]["count"] >= 1


def test_get_snapshot_route(repo):
    svc = SnapshotService(repo)
    snap = svc.create_snapshot(asset_id="asset_1", version_id="v1", manifest_digest="s1")
    result = get_snapshot_route(svc, snap.id, request_id="req_get")
    assert result["data"]["id"] == snap.id


def test_get_snapshot_route_not_found(repo):
    svc = SnapshotService(repo)
    result = get_snapshot_route(svc, "nonexistent", request_id="req_nf")
    assert result["error"]["code"] == "not_found"


def test_promote_snapshot_route(repo):
    svc = SnapshotService(repo)
    snap = svc.create_snapshot(asset_id="asset_1", version_id="v1", manifest_digest="s1", channel_name="staging")
    result = promote_snapshot_route(svc, request_id="req_promo", snapshot_id=snap.id, channel_name="staging")
    assert result["data"]["to_snapshot_id"] == snap.id


def test_promote_snapshot_route_missing_fields(repo):
    svc = SnapshotService(repo)
    result = promote_snapshot_route(svc, request_id="req_promo")
    assert result["error"]["code"] == "validation_error"


def test_rollback_snapshot_route(repo):
    svc = SnapshotService(repo)
    snap1 = svc.create_snapshot(asset_id="asset_1", version_id="v1", manifest_digest="s1", channel_name="production")
    snap2 = svc.create_snapshot(asset_id="asset_1", version_id="v2", manifest_digest="s2", channel_name="production")
    svc.promote_snapshot(snapshot_id=snap1.id, channel_name="production")
    svc.promote_snapshot(snapshot_id=snap2.id, channel_name="production")

    result = rollback_snapshot_route(svc, snap2.id, request_id="req_rb", reason="bug", rolled_back_by="admin")
    assert result["data"]["to_snapshot_id"] == snap1.id


def test_snapshot_history_route(repo):
    svc = SnapshotService(repo)
    snap = svc.create_snapshot(asset_id="asset_1", version_id="v1", manifest_digest="s1")
    result = snapshot_history_route(svc, snap.id, request_id="req_hist")
    assert result["data"]["snapshot_id"] == snap.id
    assert isinstance(result["data"]["history"], list)
