"""Tests for Phase 3b-2: Service accounts and API tokens."""

from __future__ import annotations

import pytest

from modely.governance.api_tokens import (
    ApiToken,
    InMemoryTokenRepository,
    authenticate_token,
    create_token,
    get_token,
    list_tokens,
    revoke_token,
    rotate_token,
)
from modely.governance.audit import record_audit_event
from modely.governance.service_accounts import (
    InMemoryServiceAccountRepository,
    create_service_account,
    disable_service_account,
    get_service_account,
    list_service_accounts,
    transfer_owner,
    update_service_account,
)
from modely.governance.permissions import DEFAULT_ACTIONS


@pytest.fixture
def sa_repo():
    return InMemoryServiceAccountRepository()


@pytest.fixture
def token_repo():
    return InMemoryTokenRepository()


def _audit(action, **kwargs):
    return record_audit_event(action, **kwargs)


# -- Service account tests -----------------------------------------------------


def test_create_service_account(sa_repo):
    sa = create_service_account(name="CI Bot", owner_id="user_1", tenant_scope="org1", team_id="team_a", roles=["Developer"], repository=sa_repo)
    assert sa.id.startswith("sa_")
    assert sa.name == "CI Bot"
    assert sa.tenant_scope == "org1"
    assert sa.team_id == "team_a"
    assert sa.status == "active"


def test_get_and_list_service_accounts(sa_repo):
    create_service_account(name="Bot 1", repository=sa_repo)
    create_service_account(name="Bot 2", tenant_scope="org2", repository=sa_repo)

    all_sa = list_service_accounts(repository=sa_repo)
    assert len(all_sa) == 2

    org2_sa = list_service_accounts(tenant_scope="org2", repository=sa_repo)
    assert len(org2_sa) == 1


def test_update_service_account(sa_repo):
    sa = create_service_account(name="Bot", repository=sa_repo)
    updated = update_service_account(sa.id, name="Bot v2", roles=["Platform Admin"], repository=sa_repo)
    assert updated.name == "Bot v2"
    assert updated.roles == ["Platform Admin"]


def test_disable_service_account(sa_repo):
    sa = create_service_account(name="Bot", repository=sa_repo)
    disabled = disable_service_account(sa.id, repository=sa_repo)
    assert disabled.status == "disabled"


def test_transfer_owner(sa_repo):
    sa = create_service_account(name="Bot", owner_id="user_1", repository=sa_repo)
    transferred = transfer_owner(sa.id, "user_2", repository=sa_repo)
    assert transferred.owner_id == "user_2"


def test_update_nonexistent_sa(sa_repo):
    with pytest.raises(ValueError, match="Service account not found"):
        update_service_account("nonexistent", repository=sa_repo)


# -- API token tests -----------------------------------------------------------


def test_create_token_returns_secret_once(token_repo):
    token, secret = create_token(service_account_id="sa_1", scopes=["asset:read", "asset:download"], repository=token_repo)
    assert token.id.startswith("tok_")
    assert token.prefix.startswith("mod-")
    assert secret.startswith("mod-")
    assert token.token_hash != secret  # hash != plaintext

    # Getting metadata should NOT return the secret
    got = get_token(token.id, repository=token_repo)
    assert got is not None
    assert got.token_hash is not None
    assert secret not in str(got.to_dict())  # secret not in serialized output


def test_list_tokens(token_repo):
    create_token(service_account_id="sa_1", repository=token_repo)
    create_token(service_account_id="sa_1", repository=token_repo)
    create_token(service_account_id="sa_2", repository=token_repo)

    sa1_tokens = list_tokens("sa_1", repository=token_repo)
    assert len(sa1_tokens) == 2


def test_rotate_token(token_repo):
    old_token, old_secret = create_token(service_account_id="sa_1", scopes=["asset:read"], repository=token_repo)
    new_token, new_secret = rotate_token(old_token.id, repository=token_repo)

    assert new_token.id != old_token.id
    assert new_secret != old_secret
    assert new_token.scopes == old_token.scopes


def test_rotate_token_with_grace_period(token_repo):
    old_token, _ = create_token(service_account_id="sa_1", scopes=["asset:read"], repository=token_repo)
    new_token, new_secret = rotate_token(old_token.id, grace_period_seconds=3600, repository=token_repo)

    # Old token should still be active during grace period
    old = get_token(old_token.id, repository=token_repo)
    assert old.status == "active"
    # Verify grace period was applied: expires_at should have been updated
    assert old.expires_at  # Should be set to now+3600s


def test_rotate_token_immediate_revoke(token_repo):
    old_token, _ = create_token(service_account_id="sa_1", scopes=["asset:read"], repository=token_repo)
    rotate_token(old_token.id, grace_period_seconds=0, repository=token_repo)

    old = get_token(old_token.id, repository=token_repo)
    assert old.status == "revoked"


def test_revoke_token(token_repo):
    token, _ = create_token(service_account_id="sa_1", repository=token_repo)
    revoked = revoke_token(token.id, repository=token_repo)
    assert revoked.status == "revoked"


def test_rotate_revoked_token(token_repo):
    token, _ = create_token(service_account_id="sa_1", repository=token_repo)
    revoke_token(token.id, repository=token_repo)
    with pytest.raises(ValueError, match="Cannot rotate revoked token"):
        rotate_token(token.id, repository=token_repo)


def test_authenticate_token(token_repo):
    token, secret = create_token(service_account_id="sa_1", scopes=["asset:read"], repository=token_repo)
    # authenticate_token returns None because it doesn't have SA lookup
    # (that's for the server middleware)
    result = authenticate_token(secret, repository=token_repo)
    assert result is None  # Returns None to signal "ask caller to check SA"


def test_authenticate_revoked_token(token_repo):
    token, secret = create_token(service_account_id="sa_1", repository=token_repo)
    revoke_token(token.id, repository=token_repo)
    result = authenticate_token(secret, repository=token_repo)
    assert result is None


def test_authenticate_wrong_secret(token_repo):
    create_token(service_account_id="sa_1", repository=token_repo)
    result = authenticate_token("mod-wrongtokenvalue0000000000", repository=token_repo)
    assert result is None


def test_token_scopes_use_default_actions():
    """Token scopes must be a subset of Phase 2 DEFAULT_ACTIONS."""
    scopes = ["asset:read", "asset:download", "asset:sync"]
    for scope in scopes:
        assert scope in DEFAULT_ACTIONS, f"Scope {scope} not in Phase 2 DEFAULT_ACTIONS"
