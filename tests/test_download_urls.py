"""Unit tests for modely.storage.download_urls — authorize, sign, verify, local URLs."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

from modely.domain.tenants import TenantScope
from modely.governance.rbac import Principal
from modely.storage.download_urls import (
    DownloadURL,
    _asset_to_policy_dict,
    _has_valid_approval,
    _principal_to_policy_dict,
    authorize_download,
    authorize_download_full,
    generate_signed_url,
    local_download_url,
    verify_signed_url,
)


# ---------------------------------------------------------------------------
# Test asset object that supports both getattr and to_dict
# ---------------------------------------------------------------------------

@dataclass
class _TestAsset:
    """A minimal asset-like object compatible with check_visibility and
    _asset_to_policy_dict."""

    id: str
    repo_id: str = ""
    repo_type: str = "model"
    source: str = "hf"
    license: str = "apache-2.0"
    tags: list = field(default_factory=list)
    files: list = field(default_factory=list)
    size: int = 0
    file_count: int = 0
    checksum: str = ""
    operational_state: str = "published"
    visibility: str = "organization"
    tenant_scope: Any = None
    owner_principal_id: str | None = None
    authorized_principals: frozenset = field(default_factory=frozenset)
    metadata: dict = field(default_factory=dict)
    scan_evidence: dict = field(default_factory=dict)
    approval_state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant_scope():
    """A shared tenant scope for scoped visibility checks."""
    return TenantScope(organization_id="org-1", workspace_id="ws-1")


@pytest.fixture
def dev_principal(tenant_scope):
    """A developer principal with asset:download permission and tenant scope."""
    return Principal(
        id="dev-1",
        roles=["Developer"],
        tenant_scope=tenant_scope,
    )


@pytest.fixture
def viewer_principal(tenant_scope):
    """A viewer principal without asset:download permission and tenant scope."""
    return Principal(
        id="viewer-1",
        roles=["Viewer"],
        tenant_scope=tenant_scope,
    )


@pytest.fixture
def shared_secret():
    return "test-secret-key-42"


@pytest.fixture
def organization_asset():
    """An asset with organization visibility, accessible to Developers."""
    return _TestAsset(
        id="asset-abc",
        repo_id="org/model-v1",
        repo_type="model",
        source="hf",
        license="apache-2.0",
        tags=["nlp"],
        files=["model.bin"],
        visibility="organization",
        operational_state="published",
        size=1024,
        file_count=1,
        scan_evidence={},
        approval_state={"status": "none"},
    )


# ---------------------------------------------------------------------------
# 1. authorize_download() — Developer can download, Viewer cannot
# ---------------------------------------------------------------------------

def test_authorize_download_developer_allowed(dev_principal):
    """Developer role includes asset:download, so authorize_download returns True."""
    result = authorize_download(dev_principal, "asset-123")
    assert result is True


def test_authorize_download_viewer_denied(viewer_principal):
    """Viewer role does NOT include asset:download, so authorize_download returns False."""
    result = authorize_download(viewer_principal, "asset-123")
    assert result is False


# ---------------------------------------------------------------------------
# 2. authorize_download_full() — RBAC check, visibility check, audit emission
# ---------------------------------------------------------------------------

def test_authorize_download_full_developer_success(dev_principal, organization_asset):
    """A Developer passes RBAC, visibility, and policy checks."""
    authorized, reason, audit_md = authorize_download_full(dev_principal, organization_asset)
    assert authorized is True
    assert reason == "authorized"
    assert audit_md["status"] in ("ok",) or audit_md.get("status") == "ok"
    assert "principal_id" in audit_md.get("metadata", {})


def test_authorize_download_full_emits_audit_on_allow(dev_principal, organization_asset):
    """On allow, the returned audit metadata includes status=ok."""
    authorized, reason, audit_md = authorize_download_full(dev_principal, organization_asset)
    assert authorized is True
    assert audit_md.get("status") == "ok"


def test_authorize_download_full_emits_audit_on_deny(viewer_principal, organization_asset):
    """On deny (missing permission), the returned audit metadata includes status=denied."""
    authorized, reason, audit_md = authorize_download_full(viewer_principal, organization_asset)
    assert authorized is False
    assert audit_md.get("status") == "denied"


# ---------------------------------------------------------------------------
# 3. authorize_download_full() — unauthenticated, denied by permission,
#    denied by visibility
# ---------------------------------------------------------------------------

def test_authorize_download_full_unauthenticated(organization_asset):
    """None principal yields 'unauthenticated' reason."""
    authorized, reason, audit_md = authorize_download_full(None, organization_asset)
    assert authorized is False
    assert reason == "unauthenticated"


def test_authorize_download_full_missing_permission(viewer_principal, organization_asset):
    """Viewer role lacks asset:download, so it should be denied with a
    'missing permission' reason."""
    authorized, reason, audit_md = authorize_download_full(viewer_principal, organization_asset)
    assert authorized is False
    assert "missing permission" in reason


def test_authorize_download_full_visibility_denied(dev_principal):
    """An asset with visibility='private' owned by someone else should fail
    visibility check for a non-owner Developer."""
    private_asset = _TestAsset(
        id="private-asset",
        repo_id="org/secret-model",
        visibility="private",
        owner_principal_id="admin-id",  # not dev-1
        scan_evidence={},
        approval_state={"status": "none"},
    )
    authorized, reason, audit_md = authorize_download_full(dev_principal, private_asset)
    assert authorized is False
    assert "visibility" in reason.lower()


# ---------------------------------------------------------------------------
# 4. generate_signed_url() — produces valid HMAC-SHA256 signature
# ---------------------------------------------------------------------------

def test_generate_signed_url_valid_signature(shared_secret):
    """generate_signed_url produces a URL whose signature can be independently verified."""
    with patch("time.time") as mock_time:
        mock_time.return_value = 100000.0

        result = generate_signed_url(
            asset_id="asset-1",
            principal_id="dev-1",
            storage_path="/data/models/asset-1",
            shared_secret=shared_secret,
        )

    assert isinstance(result, DownloadURL)
    assert "signature=" in result.url

    # Extract signature from URL and verify independently
    url_parts = result.url.split("&")
    params = {}
    for part in url_parts:
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.split("?")[-1] if "?" in k else k] = v

    ts = params.get("ts", "")
    sig = params.get("signature", "")

    expected = hmac.new(
        shared_secret.encode("utf-8"),
        f"asset-1:dev-1:{ts}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert hmac.compare_digest(expected, sig)


# ---------------------------------------------------------------------------
# 5. generate_signed_url() — correct TTL, correct URL structure
# ---------------------------------------------------------------------------

def test_generate_signed_url_ttl_and_structure(shared_secret):
    """The URL has the correct base structure, TTL-based expiry, and metadata."""
    base_url = "https://mirror.example.com"
    with patch("time.time") as mock_time:
        mock_time.return_value = 100000.0

        result = generate_signed_url(
            asset_id="asset-2",
            principal_id="dev-2",
            storage_path="/data/models/asset-2",
            shared_secret=shared_secret,
            ttl_seconds=600,
            base_url=base_url,
        )

    # URL structure
    assert result.url.startswith(f"{base_url}/api/v1/assets/asset-2/download")
    assert "signature=" in result.url
    assert "principal_id=dev-2" in result.url
    assert "ts=" in result.url

    # TTL
    assert result.metadata["ttl_seconds"] == 600
    assert result.expires_at is not None

    # Metadata
    assert result.metadata["backend"] == "signed"
    assert result.metadata["principal_id"] == "dev-2"


# ---------------------------------------------------------------------------
# 6. verify_signed_url() — valid signature passes, expired TTL fails,
#    wrong signature fails
# ---------------------------------------------------------------------------

def test_verify_signed_url_valid(shared_secret):
    """A correctly signed URL verifies successfully within its TTL."""
    ts = int(time.time())
    signature_base = f"asset-3:dev-3:{ts}"
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        signature_base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert verify_signed_url(
        asset_id="asset-3",
        principal_id="dev-3",
        timestamp=str(ts),
        signature=signature,
        shared_secret=shared_secret,
        max_age_seconds=300,
    ) is True


def test_verify_signed_url_expired(shared_secret):
    """A signature older than max_age_seconds is rejected."""
    ts = int(time.time()) - 400  # 400s ago, with max_age=300
    signature_base = f"asset-4:dev-4:{ts}"
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        signature_base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert verify_signed_url(
        asset_id="asset-4",
        principal_id="dev-4",
        timestamp=str(ts),
        signature=signature,
        shared_secret=shared_secret,
        max_age_seconds=300,
    ) is False


def test_verify_signed_url_wrong_signature(shared_secret):
    """A tampered signature must be rejected."""
    ts = int(time.time())
    wrong_sig = "a" * 64  # wrong HMAC-SHA256 hex digest

    assert verify_signed_url(
        asset_id="asset-5",
        principal_id="dev-5",
        timestamp=str(ts),
        signature=wrong_sig,
        shared_secret=shared_secret,
        max_age_seconds=300,
    ) is False


def test_verify_signed_url_wrong_principal(shared_secret):
    """A signature generated for a different principal must not verify."""
    ts = int(time.time())
    # Sign for dev-A but try to verify as dev-B
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        f"asset-6:dev-A:{ts}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert verify_signed_url(
        asset_id="asset-6",
        principal_id="dev-B",
        timestamp=str(ts),
        signature=signature,
        shared_secret=shared_secret,
        max_age_seconds=300,
    ) is False


# ---------------------------------------------------------------------------
# 7. verify_signed_url() — invalid timestamp format
# ---------------------------------------------------------------------------

def test_verify_signed_url_invalid_timestamp(shared_secret):
    """A non-integer timestamp string must be rejected (returns False)."""
    assert verify_signed_url(
        asset_id="asset-7",
        principal_id="dev-7",
        timestamp="not-a-number",
        signature="a" * 64,
        shared_secret=shared_secret,
    ) is False


def test_verify_signed_url_none_timestamp(shared_secret):
    """A None timestamp must be rejected gracefully."""
    assert verify_signed_url(
        asset_id="asset-7",
        principal_id="dev-7",
        timestamp=None,
        signature="a" * 64,
        shared_secret=shared_secret,
    ) is False


# ---------------------------------------------------------------------------
# 8. local_download_url() — correct file:// URL format
# ---------------------------------------------------------------------------

def test_local_download_url_format():
    """local_download_url returns a DownloadURL with file:// scheme."""
    result = local_download_url("/models/bert-base")
    assert isinstance(result, DownloadURL)
    assert result.url == "file:///models/bert-base"
    assert result.expires_at is None
    assert result.method == "GET"
    assert result.metadata["backend"] == "local"


def test_local_download_url_relative_path():
    """local_download_url preserves relative paths in the file:// URL."""
    result = local_download_url("data/cache/model")
    assert result.url == "file://data/cache/model"


# ---------------------------------------------------------------------------
# 9. DownloadURL dataclass — to_dict() works
# ---------------------------------------------------------------------------

def test_download_url_to_dict():
    """DownloadURL.to_dict() returns a plain dict with all fields."""
    dl = DownloadURL(
        url="https://example.com/dl",
        expires_at="2026-01-01T00:00:00+00:00",
        method="POST",
        headers={"X-Token": "abc"},
        metadata={"source": "hf"},
    )
    d = dl.to_dict()
    assert d["url"] == "https://example.com/dl"
    assert d["expires_at"] == "2026-01-01T00:00:00+00:00"
    assert d["method"] == "POST"
    assert d["headers"] == {"X-Token": "abc"}
    assert d["metadata"] == {"source": "hf"}


def test_download_url_to_dict_defaults():
    """DownloadURL defaults serialize correctly via to_dict."""
    dl = DownloadURL(url="http://a")
    d = dl.to_dict()
    assert d["url"] == "http://a"
    assert d["expires_at"] is None
    assert d["method"] == "GET"
    assert d["headers"] == {}
    assert d["metadata"] == {}


# ---------------------------------------------------------------------------
# 10. _asset_to_policy_dict() — converts dataclass, dict, and generic objects
# ---------------------------------------------------------------------------

def test_asset_to_policy_dict_from_dataclass():
    """Converts a dataclass asset with to_dict() method."""
    asset = _TestAsset(id="a1", repo_id="org/r", source="hf", license="mit")
    result = _asset_to_policy_dict(asset)
    assert result["id"] == "a1"
    assert result["repo_id"] == "org/r"
    assert result["source"] == "hf"
    assert result["license"] == "mit"


def test_asset_to_policy_dict_from_dict():
    """Converts a plain dict asset."""
    asset = {"id": "a2", "repo_id": "org/r2", "license": "apache-2.0"}
    result = _asset_to_policy_dict(asset)
    assert result["id"] == "a2"
    assert result["license"] == "apache-2.0"


def test_asset_to_policy_dict_from_generic_object():
    """Converts a generic object with attributes (no to_dict)."""

    class GenericAsset:
        id = "a3"
        repo_id = "org/r3"
        source = "ms"
        license = "gpl-3.0"
        tags = ["nlp"]
        files = ["f1.bin"]
        size = 2048
        file_count = 1
        operational_state = "published"
        visibility = "organization"
        scan = {"security": "ok"}

    result = _asset_to_policy_dict(GenericAsset())
    assert result["id"] == "a3"
    assert result["source"] == "ms"
    assert result["license"] == "gpl-3.0"


# ---------------------------------------------------------------------------
# 11. _principal_to_policy_dict() — converts principal objects to dict
# ---------------------------------------------------------------------------

def test_principal_to_policy_dict_from_rbac_principal():
    """Converts a Principal dataclass with to_dict()."""
    from modely.governance.rbac import Principal as RbacPrincipal

    p = RbacPrincipal(id="p1", roles=["Developer"])
    result = _principal_to_policy_dict(p)
    assert result["id"] == "p1"
    assert result["roles"] == ["Developer"]


def test_principal_to_policy_dict_from_dict():
    """Converts a plain dict principal."""
    p = {"id": "p2", "username": "bob", "department": "eng"}
    result = _principal_to_policy_dict(p)
    assert result["id"] == "p2"
    assert result["department"] == "eng"


def test_principal_to_policy_dict_from_generic_object():
    """Converts a generic object with attributes."""

    class GenericPrincipal:
        id = "p3"
        username = "carol"
        department = "ml"
        email = "carol@example.com"

    result = _principal_to_policy_dict(GenericPrincipal())
    assert result["id"] == "p3"
    assert result["department"] == "ml"


# ---------------------------------------------------------------------------
# 12. _has_valid_approval() — approval state checks
# ---------------------------------------------------------------------------

def test_has_valid_approval_approved_no_expiry():
    """Approved status with no expires_at is valid."""
    assert _has_valid_approval({"status": "approved"}) is True


def test_has_valid_approval_approved_not_expired():
    """Approved status with future expires_at is valid."""
    from datetime import datetime, timedelta, timezone

    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    assert _has_valid_approval({"status": "approved", "expires_at": future}) is True


def test_has_valid_approval_expired():
    """Approved status with past expires_at is invalid."""
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert _has_valid_approval({"status": "approved", "expires_at": past}) is False


def test_has_valid_approval_pending():
    """Pending status is not valid even without expiry."""
    assert _has_valid_approval({"status": "pending_approval"}) is False


def test_has_valid_approval_none_status():
    """None/suppressed status is not valid."""
    assert _has_valid_approval({"status": "none"}) is False


def test_has_valid_approval_not_dict():
    """Non-dict input returns False."""
    assert _has_valid_approval("not-a-dict") is False
    assert _has_valid_approval(None) is False
    assert _has_valid_approval(42) is False


def test_has_valid_approval_unparseable_expiry():
    """An unparseable expires_at string returns False."""
    assert _has_valid_approval({"status": "approved", "expires_at": "not-a-date"}) is False


# ---------------------------------------------------------------------------
# 13. authorize_download_full() — policy block and require_approval paths
# ---------------------------------------------------------------------------

def test_authorize_download_full_policy_blocked(dev_principal, organization_asset):
    """When policy engine returns blocked=True, download is denied."""
    from modely.governance.policy_engine import PolicyDecision

    block_decision = PolicyDecision(
        outcome="block",
        reasons=["license risk: non-commercial"],
        matched_rule_ids=["rule-001"],
    )

    with patch("modely.governance.policy_engine.evaluate_governance_policy") as mock_eval:
        mock_eval.return_value = block_decision

        authorized, reason, audit_md = authorize_download_full(
            dev_principal, organization_asset
        )

        assert authorized is False
        assert "policy_blocked" in reason
        assert audit_md.get("status") == "denied"
        assert audit_md.get("policy_outcome") == "block"
        assert audit_md.get("policy_rule_ids") == ["rule-001"]


def test_authorize_download_full_require_approval_no_valid_approval(dev_principal):
    """When policy requires approval but none exists, download is denied."""
    from modely.governance.policy_engine import PolicyDecision

    req_decision = PolicyDecision(
        outcome="require_approval",
        reasons=["vulnerability count exceeds threshold"],
        matched_rule_ids=["rule-002"],
    )

    asset = _TestAsset(
        id="asset-needs-approval",
        visibility="organization",
        approval_state={"status": "none"},
        scan_evidence={},
    )

    with patch("modely.governance.policy_engine.evaluate_governance_policy") as mock_eval:
        mock_eval.return_value = req_decision

        authorized, reason, audit_md = authorize_download_full(
            dev_principal, asset
        )

        assert authorized is False
        assert "approval_required" in reason
        assert audit_md.get("status") == "denied"
        assert audit_md.get("policy_outcome") == "require_approval"
        assert audit_md.get("policy_rule_ids") == ["rule-002"]


def test_authorize_download_full_require_approval_with_valid_approval(dev_principal):
    """When policy requires approval and one exists, download is allowed."""
    from modely.governance.policy_engine import PolicyDecision

    req_decision = PolicyDecision(
        outcome="require_approval",
        reasons=["vulnerability count exceeds threshold"],
        matched_rule_ids=["rule-003"],
    )

    asset = _TestAsset(
        id="asset-has-approval",
        visibility="organization",
        approval_state={"status": "approved"},
        scan_evidence={},
    )

    with patch("modely.governance.policy_engine.evaluate_governance_policy") as mock_eval:
        mock_eval.return_value = req_decision

        authorized, reason, audit_md = authorize_download_full(
            dev_principal, asset
        )

        assert authorized is True
        assert "authorized" in reason


def test_authorize_download_full_with_shared_secret(dev_principal, organization_asset, shared_secret):
    """When shared_secret is provided, signature_base is included in audit."""
    with patch("time.time") as mock_time:
        mock_time.return_value = 100000.0

        authorized, reason, audit_md = authorize_download_full(
            dev_principal, organization_asset, shared_secret=shared_secret
        )

        assert authorized is True
        assert "signature_base" in audit_md
        assert "signature_timestamp" in audit_md
        assert audit_md["signature_base"].startswith("asset-abc:dev-1:")


def test_authorize_download_full_policy_warn(dev_principal, organization_asset):
    """When policy returns warn, download is still authorized with warning in audit."""
    from modely.governance.policy_engine import PolicyDecision

    warn_decision = PolicyDecision(
        outcome="warn",
        reasons=["license risk: uncertain"],
        matched_rule_ids=["rule-004"],
    )

    with patch("modely.governance.policy_engine.evaluate_governance_policy") as mock_eval:
        mock_eval.return_value = warn_decision

        authorized, reason, audit_md = authorize_download_full(
            dev_principal, organization_asset
        )

        assert authorized is True
        assert reason == "authorized"  # the return value is always "authorized"
        assert audit_md.get("status") == "ok"
        assert audit_md.get("policy_outcome") == "warn"
        assert audit_md.get("policy_rule_ids") == ["rule-004"]
        # warn reason details appear in audit metadata
        assert "policy_reasons" in audit_md
