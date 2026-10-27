"""Unit tests for governance and admin server routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from modely.server.routes.governance import (
    approve_request,
    cancel_request,
    create_service_account_route,
    create_token_route,
    disable_service_account_route,
    evaluate_policy,
    get_request,
    get_service_account_route,
    get_token_route,
    list_requests,
    list_service_accounts_route,
    list_tokens_route,
    reject_request,
    revoke_token_route,
    rotate_token_route,
    submit_approval,
)
from modely.server.routes.admin import (
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


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _PolicyDecision:
    """Test double for a policy decision entity."""
    def __init__(self, **kwargs):
        self._data = kwargs or {"allowed": True, "reason": "ok"}

    def to_dict(self):
        return dict(self._data)


class _Approval:
    """Test double for an approval request entity."""
    def __init__(self, **kwargs):
        self._data = kwargs or {
            "id": "req_1",
            "status": "pending",
            "asset_id": "hf/user/repo",
        }

    def to_dict(self):
        return dict(self._data)


class _Quota:
    """Test double for a quota entity."""
    def __init__(self, **kwargs):
        self._data = kwargs or {
            "id": "q_1",
            "subject": "tenant/default",
            "dimension": "downloads_per_day",
            "limit": 1000,
            "token": "should-be-redacted",
        }

    def to_dict(self):
        return dict(self._data)


class _Credential:
    """Test double for a credential entity."""
    def __init__(self, **kwargs):
        self._data = kwargs or {
            "id": "cred_1",
            "source": "huggingface",
            "secret_ref": "vault:hf/prod-read",
            "owner_principal": "user_1",
            "owner_team": "ml-eng",
            "tenant_scope": "default",
            "created_at": "2025-01-01T00:00:00Z",
        }

    def to_dict(self):
        return dict(self._data)


class _Principal:
    """Test double for a principal with tenant scope and allowed actions."""
    def __init__(self, tenant_scope="default", allowed_actions=None):
        self.tenant_scope = tenant_scope
        self.allowed_actions = allowed_actions or set()


class _ServiceAccount:
    """Test double for a service account entity."""
    def __init__(self, **kwargs):
        self._data = kwargs or {
            "id": "sa_1",
            "name": "ml-pipeline",
            "owner_id": "user_1",
            "tenant_scope": "default",
            "roles": ["Viewer"],
            "status": "active",
            "created_at": "2025-01-01T00:00:00Z",
        }

    def to_dict(self):
        return dict(self._data)


class _APIToken:
    """Test double for an API token entity."""
    def __init__(self, **kwargs):
        self._data = kwargs or {
            "id": "tok_1",
            "service_account_id": "sa_1",
            "scopes": ["asset:read"],
            "expires_at": "2027-01-01T00:00:00Z",
            "status": "active",
            "created_at": "2025-01-01T00:00:00Z",
        }

    def to_dict(self):
        return dict(self._data)


# ---------------------------------------------------------------------------
# Governance route tests
# ---------------------------------------------------------------------------

class TestGovernanceRoutes:
    """Tests for governance route adapters in routes/governance.py."""

    # -- evaluate_policy ---------------------------------------------------

    def test_evaluate_policy_calls_service_and_returns_to_dict(self):
        """evaluate_policy() calls service.evaluate_policy and returns to_dict result."""
        decision = _PolicyDecision(allowed=False, reason="quota exceeded")
        service = MagicMock()
        service.evaluate_policy.return_value = decision

        result = evaluate_policy(service, {"asset_id": "hf/u/r", "action": "download"})

        service.evaluate_policy.assert_called_once_with(
            {"asset_id": "hf/u/r", "action": "download"}
        )
        assert result == {"allowed": False, "reason": "quota exceeded"}

    # -- submit_approval ---------------------------------------------------

    def test_submit_approval_calls_service_and_returns_to_dict(self):
        """submit_approval() calls service.submit_approval and returns to_dict result."""
        approval = _Approval(id="req_2", status="pending_approval")
        service = MagicMock()
        service.submit_approval.return_value = approval

        result = submit_approval(service, {"asset_id": "hf/u/r", "requester": "alice"})

        service.submit_approval.assert_called_once_with(
            {"asset_id": "hf/u/r", "requester": "alice"}
        )
        assert result == {"id": "req_2", "status": "pending_approval"}

    # -- approve_request ---------------------------------------------------

    def test_approve_request_calls_service_approve_with_reviewer_and_reason(self):
        """approve_request() calls service.approve with reviewer and reason."""
        approval = _Approval(id="req_3", status="approved")
        service = MagicMock()
        service.approve.return_value = approval

        result = approve_request(
            service,
            "req_3",
            payload={"reviewer": "bob", "reason": "safe model"},
        )

        service.approve.assert_called_once_with(
            "req_3", reviewer="bob", reason="safe model"
        )
        assert result == {"id": "req_3", "status": "approved"}

    def test_approve_request_without_payload_defaults_to_none(self):
        """approve_request() works when payload is None."""
        approval = _Approval(id="req_3", status="approved")
        service = MagicMock()
        service.approve.return_value = approval

        result = approve_request(service, "req_3")

        service.approve.assert_called_once_with(
            "req_3", reviewer=None, reason=None
        )
        assert result["id"] == "req_3"

    # -- reject_request ----------------------------------------------------

    def test_reject_request_calls_service_reject_with_reviewer_and_reason(self):
        """reject_request() calls service.reject with reviewer and reason."""
        approval = _Approval(id="req_4", status="rejected")
        service = MagicMock()
        service.reject.return_value = approval

        result = reject_request(
            service,
            "req_4",
            payload={"reviewer": "carol", "reason": "untrusted source"},
        )

        service.reject.assert_called_once_with(
            "req_4", reviewer="carol", reason="untrusted source"
        )
        assert result == {"id": "req_4", "status": "rejected"}

    def test_reject_request_without_payload_defaults_to_none(self):
        """reject_request() works when payload is empty."""
        approval = _Approval(id="req_4", status="rejected")
        service = MagicMock()
        service.reject.return_value = approval

        result = reject_request(service, "req_4", payload={})

        service.reject.assert_called_once_with(
            "req_4", reviewer=None, reason=None
        )
        assert result["id"] == "req_4"

    # -- cancel_request ----------------------------------------------------

    def test_cancel_request_calls_service_cancel(self):
        """cancel_request() calls service.cancel with request_id."""
        approval = _Approval(id="req_5", status="cancelled")
        service = MagicMock()
        service.cancel.return_value = approval

        result = cancel_request(service, "req_5")

        service.cancel.assert_called_once_with("req_5")
        assert result == {"id": "req_5", "status": "cancelled"}

    # -- list_requests -----------------------------------------------------

    def test_list_requests_calls_service_list_requests_with_filters(self):
        """list_requests() calls service.list_requests with filters and returns list."""
        req_a = _Approval(id="req_a", status="pending")
        req_b = _Approval(id="req_b", status="approved")
        service = MagicMock()
        service.list_requests.return_value = [req_a, req_b]

        result = list_requests(service, {"status": "pending"})

        service.list_requests.assert_called_once_with({"status": "pending"})
        assert result["total"] == 2
        assert result["requests"] == [
            {"id": "req_a", "status": "pending"},
            {"id": "req_b", "status": "approved"},
        ]

    def test_list_requests_with_no_filters(self):
        """list_requests() works with None filters (defaults to empty dict)."""
        service = MagicMock()
        service.list_requests.return_value = []

        result = list_requests(service)

        service.list_requests.assert_called_once_with({})
        assert result == {"requests": [], "total": 0}

    # -- get_request -------------------------------------------------------

    def test_get_request_calls_service_get_request_with_id(self):
        """get_request() calls service.get_request and returns to_dict."""
        approval = _Approval(id="req_7", status="pending_approval")
        service = MagicMock()
        service.get_request.return_value = approval

        result = get_request(service, "req_7")

        service.get_request.assert_called_once_with("req_7")
        assert result == {"id": "req_7", "status": "pending_approval"}


# ---------------------------------------------------------------------------
# Service account and token route tests
# ---------------------------------------------------------------------------

class TestServiceAccountTokenRoutes:
    """Tests for service account and token route adapters in routes/governance.py."""

    # -- list_service_accounts_route ---------------------------------------

    def test_list_service_accounts_route_returns_data_envelope(self):
        """list_service_accounts_route() returns data envelope with service accounts."""
        from modely.governance.service_accounts import InMemoryServiceAccountRepository

        service = MagicMock()
        repo = InMemoryServiceAccountRepository()
        service._sa_repo = repo

        # Pre-populate repo with a service account
        from modely.governance.service_accounts import create_service_account
        create_service_account(
            name="bot-a", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=repo,
        )

        result = list_service_accounts_route(service, request_id="rid_sa1")

        assert len(result["data"]["service_accounts"]) == 1
        assert result["data"]["service_accounts"][0]["name"] == "bot-a"
        assert result["meta"]["request_id"] == "rid_sa1"

    def test_list_service_accounts_route_with_filters(self):
        """list_service_accounts_route() passes tenant_scope filter."""
        from modely.governance.service_accounts import InMemoryServiceAccountRepository

        service = MagicMock()
        repo = InMemoryServiceAccountRepository()
        service._sa_repo = repo

        result = list_service_accounts_route(
            service, request_id="rid_sa2", tenant_scope="org-1"
        )
        assert result["meta"]["request_id"] == "rid_sa2"
        assert len(result["data"]["service_accounts"]) == 0

    # -- create_service_account_route --------------------------------------

    def test_create_service_account_route_returns_data_envelope(self):
        """create_service_account_route() calls create_service_account and returns envelope."""
        from modely.governance.service_accounts import InMemoryServiceAccountRepository

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()

        result = create_service_account_route(
            service,
            request_id="rid_sa3",
            name="new-bot",
            owner_id="user_x",
            tenant_scope="default",
            roles=["Editor"],
        )

        assert result["data"]["name"] == "new-bot"
        assert result["data"]["owner_id"] == "user_x"
        assert result["data"]["roles"] == ["Editor"]
        assert result["meta"]["request_id"] == "rid_sa3"

    # -- get_service_account_route -----------------------------------------

    def test_get_service_account_route_returns_data_envelope(self):
        """get_service_account_route() returns data envelope for existing SA."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )

        service = MagicMock()
        repo = InMemoryServiceAccountRepository()
        service._sa_repo = repo
        sa = create_service_account(
            name="bot-xyz", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=repo,
        )

        result = get_service_account_route(service, sa.id, request_id="rid_sa4")

        assert result["data"]["id"] == sa.id
        assert result["data"]["name"] == "bot-xyz"
        assert result["meta"]["request_id"] == "rid_sa4"

    def test_get_service_account_route_not_found(self):
        """get_service_account_route() returns error envelope when SA not found."""
        from modely.governance.service_accounts import InMemoryServiceAccountRepository

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()

        result = get_service_account_route(service, "sa_missing", request_id="rid_sa5")

        assert "error" in result
        assert result["error"]["code"] == "not_found"
        assert result["error"]["request_id"] == "rid_sa5"

    # -- disable_service_account_route -------------------------------------

    def test_disable_service_account_route_returns_data_envelope(self):
        """disable_service_account_route() calls disable and returns envelope."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )

        service = MagicMock()
        repo = InMemoryServiceAccountRepository()
        service._sa_repo = repo
        sa = create_service_account(
            name="old-bot", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=repo,
        )

        result = disable_service_account_route(service, sa.id, request_id="rid_sa6")

        assert result["data"]["id"] == sa.id
        assert result["data"]["status"] == "disabled"
        assert result["meta"]["request_id"] == "rid_sa6"

    # -- create_token_route ------------------------------------------------

    def test_create_token_route_returns_data_envelope_with_secret(self):
        """create_token_route() returns token data with plaintext secret."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-tok", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )

        result = create_token_route(service, sa.id, request_id="rid_tok1")

        assert result["data"]["service_account_id"] == sa.id
        assert "token" in result["data"]
        assert len(result["data"]["token"]) > 0
        assert result["meta"]["request_id"] == "rid_tok1"

    def test_create_token_route_passes_scopes_and_expiry(self):
        """create_token_route() passes scopes and expires_in_days to create_token."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-scope", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )

        result = create_token_route(
            service, sa.id,
            request_id="rid_tok2",
            scopes=["asset:read", "asset:write"],
            expires_in_days=180,
        )

        assert "asset:read" in result["data"]["scopes"]
        assert "asset:write" in result["data"]["scopes"]
        assert result["meta"]["request_id"] == "rid_tok2"

    # -- list_tokens_route -------------------------------------------------

    def test_list_tokens_route_returns_data_envelope(self):
        """list_tokens_route() returns data envelope with tokens."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-tok2", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = list_tokens_route(service, request_id="rid_tok3", service_account_id=sa.id)

        assert len(result["data"]["tokens"]) == 1
        assert result["data"]["tokens"][0]["service_account_id"] == sa.id
        assert result["meta"]["request_id"] == "rid_tok3"

    def test_list_tokens_route_filters_by_service_account(self):
        """list_tokens_route() passes service_account_id filter."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-filter", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = list_tokens_route(
            service,
            request_id="rid_tok4",
            service_account_id=sa.id,
        )

        assert len(result["data"]["tokens"]) == 1
        assert result["meta"]["request_id"] == "rid_tok4"

    # -- get_token_route ---------------------------------------------------

    def test_get_token_route_returns_data_envelope(self):
        """get_token_route() returns data envelope for existing token."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-tok3", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        tok, _ = create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = get_token_route(service, tok.id, request_id="rid_tok5")

        assert result["data"]["id"] == tok.id
        assert result["data"]["service_account_id"] == sa.id
        assert result["meta"]["request_id"] == "rid_tok5"

    def test_get_token_route_not_found(self):
        """get_token_route() returns error envelope when token not found."""
        from modely.governance.api_tokens import InMemoryTokenRepository

        service = MagicMock()
        service._token_repo = InMemoryTokenRepository()

        result = get_token_route(service, "tok_missing", request_id="rid_tok6")

        assert "error" in result
        assert result["error"]["code"] == "not_found"
        assert result["error"]["request_id"] == "rid_tok6"

    # -- rotate_token_route ------------------------------------------------

    def test_rotate_token_route_returns_data_envelope_with_secret(self):
        """rotate_token_route() returns new token data with plaintext secret."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-rot", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        tok, _ = create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = rotate_token_route(service, tok.id, request_id="rid_tok7")

        assert result["data"]["id"] != tok.id  # rotated — new id
        assert result["data"]["service_account_id"] == sa.id
        assert "token" in result["data"]
        assert len(result["data"]["token"]) > 0
        assert result["meta"]["request_id"] == "rid_tok7"

    def test_rotate_token_route_passes_grace_period(self):
        """rotate_token_route() passes grace_period_seconds."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-gp", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        tok, _ = create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = rotate_token_route(
            service, tok.id,
            request_id="rid_tok8",
            grace_period_seconds=600,
        )

        assert result["meta"]["request_id"] == "rid_tok8"
        assert result["data"]["id"] != tok.id

    # -- revoke_token_route ------------------------------------------------

    def test_revoke_token_route_returns_data_envelope(self):
        """revoke_token_route() returns token data envelope."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-rev", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        tok, _ = create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = revoke_token_route(service, tok.id, request_id="rid_tok9")

        assert result["data"]["id"] == tok.id
        assert result["data"]["status"] == "revoked"
        assert result["meta"]["request_id"] == "rid_tok9"

    def test_revoke_token_route_calls_revoke_token(self):
        """revoke_token_route() calls revoke_token with correct id."""
        from modely.governance.service_accounts import (
            InMemoryServiceAccountRepository,
            create_service_account,
        )
        from modely.governance.api_tokens import InMemoryTokenRepository, create_token

        service = MagicMock()
        service._sa_repo = InMemoryServiceAccountRepository()
        service._token_repo = InMemoryTokenRepository()
        sa = create_service_account(
            name="bot-rev2", owner_id="user_1", roles=["Viewer"],
            tenant_scope="default", repository=service._sa_repo,
        )
        tok, _ = create_token(service_account_id=sa.id, scopes=["asset:read"], repository=service._token_repo)

        result = revoke_token_route(service, tok.id)

        assert result["data"]["status"] == "revoked"


# ---------------------------------------------------------------------------
# Admin route tests
# ---------------------------------------------------------------------------

class TestAdminRoutes:
    """Tests for admin route adapters in routes/admin.py."""

    # -- list_quotas -------------------------------------------------------

    def test_list_quotas_returns_redacted_envelope(self):
        """list_quotas() returns redacted data envelope with request_id."""
        quota = _Quota(id="q1", limit=500, token="secret-token-abc")
        service = MagicMock()
        service.list_quotas.return_value = [quota]

        result = list_quotas(service, subject="t", dimension="d", mode="m", request_id="rid_1")

        service.list_quotas.assert_called_once_with(
            subject="t", dimension="d", mode="m"
        )
        assert result["meta"]["request_id"] == "rid_1"
        assert result["data"]["count"] == 1
        assert result["data"]["quotas"][0]["id"] == "q1"
        assert result["data"]["quotas"][0]["token"] == "<redacted>"
        assert result["data"]["quotas"][0]["limit"] == 500

    # -- get_quota ---------------------------------------------------------

    def test_get_quota_returns_redacted_envelope(self):
        """get_quota() returns redacted data envelope."""
        quota = _Quota(id="q2", subject="x", token="secret")
        service = MagicMock()
        service.get_quota.return_value = quota

        result = get_quota(service, "q2", request_id="rid_2")

        service.get_quota.assert_called_once_with("q2")
        assert result["meta"]["request_id"] == "rid_2"
        assert result["data"]["quota"]["id"] == "q2"
        assert result["data"]["quota"]["token"] == "<redacted>"

    # -- set_quota ---------------------------------------------------------

    def test_set_quota_returns_redacted_envelope(self):
        """set_quota() returns redacted data envelope."""
        quota = _Quota(id="q3", limit=200, token="new-secret")
        service = MagicMock()
        service.set_quota.return_value = quota

        result = set_quota(service, {"subject": "x", "limit": 200}, request_id="rid_3")

        service.set_quota.assert_called_once_with({"subject": "x", "limit": 200})
        assert result["meta"]["request_id"] == "rid_3"
        assert result["data"]["quota"]["limit"] == 200
        assert result["data"]["quota"]["token"] == "<redacted>"

    # -- delete_quota ------------------------------------------------------

    def test_delete_quota_returns_deleted_true(self):
        """delete_quota() returns {deleted: true} envelope."""
        service = MagicMock()

        result = delete_quota(service, "q4", request_id="rid_4")

        service.delete_quota.assert_called_once_with("q4")
        assert result == {
            "data": {"deleted": True, "quota_id": "q4"},
            "meta": {"request_id": "rid_4"},
        }

    # -- list_credentials --------------------------------------------------

    def test_list_credentials_returns_redacted_envelope(self):
        """list_credentials() returns redacted envelope without secret_ref or owner fields."""
        cred = _Credential(
            id="c1",
            source="huggingface",
            tenant_scope="default",
            secret_ref="vault:hf/prod",
            owner_principal="alice",
            owner_team="ml",
        )
        service = MagicMock()
        service.list_credentials.return_value = [cred]

        result = list_credentials(
            service,
            source="huggingface",
            tenant_scope="default",
            request_id="rid_5",
        )

        service.list_credentials.assert_called_once_with(
            source="huggingface", tenant_scope="default"
        )
        assert result["meta"]["request_id"] == "rid_5"
        assert result["data"]["count"] == 1
        cred_result = result["data"]["credentials"][0]
        assert cred_result["id"] == "c1"
        assert cred_result["source"] == "huggingface"
        assert "secret_ref" not in cred_result
        assert "owner_principal" not in cred_result
        assert "owner_team" not in cred_result

    def test_list_credentials_filters_by_principal_tenant_scope(self):
        """list_credentials() tenant-scopes results when principal is provided."""
        cred_default = _Credential(id="c1", tenant_scope="default")
        cred_org_b = _Credential(id="c2", tenant_scope="org-b")
        service = MagicMock()
        service.list_credentials.return_value = [cred_default, cred_org_b]
        principal = _Principal(tenant_scope="default")

        result = list_credentials(service, principal=principal)

        assert result["data"]["count"] == 1
        assert result["data"]["credentials"][0]["id"] == "c1"

    # -- get_credential ----------------------------------------------------

    def test_get_credential_returns_redacted_envelope(self):
        """get_credential() returns redacted envelope without secret_ref."""
        cred = _Credential(id="c3", source="modelscope", secret_ref="vault:ms/key")
        service = MagicMock()
        service.get_credential.return_value = cred

        result = get_credential(service, "c3", request_id="rid_6")

        service.get_credential.assert_called_once_with("c3")
        assert result["meta"]["request_id"] == "rid_6"
        assert result["data"]["credential"]["id"] == "c3"
        assert "secret_ref" not in result["data"]["credential"]
        assert "owner_principal" not in result["data"]["credential"]

    # -- register_credential -----------------------------------------------

    def test_register_credential_returns_redacted_envelope(self):
        """register_credential() returns redacted metadata envelope."""
        cred = _Credential(
            id="c4",
            source="kaggle",
            secret_ref="vault:kg/key",
            owner_principal="dave",
            owner_team="ds",
        )
        service = MagicMock()
        service.register_credential.return_value = cred

        result = register_credential(
            service,
            {"source": "kaggle", "api_key": "sk-1234"},
            request_id="rid_7",
        )

        service.register_credential.assert_called_once_with(
            {"source": "kaggle", "api_key": "sk-1234"}
        )
        assert result["meta"]["request_id"] == "rid_7"
        assert result["data"]["credential"]["id"] == "c4"
        assert "secret_ref" not in result["data"]["credential"]
        assert "owner_principal" not in result["data"]["credential"]

    # -- revoke_credential -------------------------------------------------

    def test_revoke_credential_returns_redacted_envelope(self):
        """revoke_credential() returns redacted metadata envelope."""
        cred = _Credential(
            id="c5",
            source="huggingface",
            secret_ref="vault:hf/old",
            owner_principal="eve",
        )
        service = MagicMock()
        service.revoke_credential.return_value = cred

        result = revoke_credential(service, "c5", request_id="rid_8")

        service.revoke_credential.assert_called_once_with("c5")
        assert result["meta"]["request_id"] == "rid_8"
        assert result["data"]["credential"]["id"] == "c5"
        assert "secret_ref" not in result["data"]["credential"]

    # -- list_audit_events_admin -------------------------------------------

    def test_list_audit_events_admin_returns_permission_filtered_envelope(self):
        """list_audit_events_admin() filters by allowed_actions and tenant scope."""
        events = [
            _PolicyDecision(action="asset:read", tenant_scope="default", detail="ok"),
            _PolicyDecision(action="token:manage", tenant_scope="default", detail="secret"),
            _PolicyDecision(action="asset:read", tenant_scope="org-b", detail="other"),
        ]
        service = MagicMock()
        service.list_audit_events.return_value = events
        principal = _Principal(
            tenant_scope="default",
            allowed_actions={"asset:read", "asset:write"},
        )

        result = list_audit_events_admin(
            service,
            action="asset:read",
            request_id="rid_9",
            principal=principal,
        )

        service.list_audit_events.assert_called_once_with(
            action="asset:read", principal_id="", asset_id="", since="", until=""
        )
        assert result["meta"]["request_id"] == "rid_9"
        # Only "asset:read" + "default" tenant should survive
        assert result["data"]["count"] == 1
        assert result["data"]["audit_events"][0]["action"] == "asset:read"
        assert result["data"]["audit_events"][0]["tenant_scope"] == "default"

    def test_list_audit_events_admin_without_principal(self):
        """list_audit_events_admin() works without a principal (no filtering)."""
        events = [
            _PolicyDecision(action="asset:read", detail="a"),
            _PolicyDecision(action="token:manage", detail="b"),
        ]
        service = MagicMock()
        service.list_audit_events.return_value = events

        result = list_audit_events_admin(service, request_id="rid_10")

        assert result["data"]["count"] == 2
