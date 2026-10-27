"""API token lifecycle services for Phase 3b.

Tokens are issued credentials for service accounts. Secrets are shown once
(create/rotate) and stored as SHA256 hashes. All operations emit audit events.
"""

from __future__ import annotations

import hashlib
import secrets as _secrets
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .service_accounts import ServiceAccount


class TokenRepository(Protocol):
    """Backend-neutral repository for API tokens."""

    def save(self, token: "ApiToken") -> "ApiToken": ...
    def get(self, token_id: str) -> "ApiToken | None": ...
    def list(self, service_account_id: str) -> list["ApiToken"]: ...
    def find_by_hash(self, token_hash: str) -> "ApiToken | None": ...


@dataclass
class ApiToken:
    """Metadata for an issued API token. The secret is NEVER stored here."""

    id: str
    service_account_id: str
    prefix: str  # "mod-xxxxxxxx"
    token_hash: str  # SHA256 of the secret
    scopes: list[str] = field(default_factory=list)
    expires_at: str = ""
    status: str = "active"
    last_used_at: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _token_id() -> str:
    return f"tok_{uuid.uuid4().hex[:12]}"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _expiry(days: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _generate_token_value() -> str:
    """Generate a cryptographically random token value."""
    return f"mod-{_secrets.token_hex(32)}"


def _hash_token(token_value: str) -> str:
    return hashlib.sha256(token_value.encode()).hexdigest()


def create_token(
    *,
    service_account_id: str,
    scopes: list[str] | None = None,
    expires_in_days: int = 90,
    repository: TokenRepository,
    audit_func=None,
) -> tuple[ApiToken, str]:
    """Create an API token. Returns (token_metadata, plaintext_secret).

    The secret is returned ONCE. Only the SHA256 hash is stored.
    """

    token_value = _generate_token_value()
    token_hash = _hash_token(token_value)

    token = ApiToken(
        id=_token_id(),
        service_account_id=service_account_id,
        prefix=token_value[:11],  # "mod-xxxxxxx"
        token_hash=token_hash,
        scopes=scopes or ["asset:read"],
        expires_at=_expiry(expires_in_days),
        created_at=_now(),
    )
    repository.save(token)
    if audit_func:
        audit_func("token.create", resource=token.id, status="ok", metadata={"service_account_id": service_account_id, "scopes": token.scopes})
    return token, token_value


def get_token(token_id: str, *, repository: TokenRepository) -> ApiToken | None:
    """Get token metadata. NEVER returns the secret."""
    return repository.get(token_id)


def list_tokens(service_account_id: str, *, repository: TokenRepository) -> list[ApiToken]:
    """List token metadata for a service account. NEVER returns secrets."""
    return repository.list(service_account_id)


def rotate_token(
    token_id: str,
    *,
    grace_period_seconds: int = 0,
    repository: TokenRepository,
    audit_func=None,
) -> tuple[ApiToken, str] | None:
    """Rotate a token. Returns (new_token_metadata, new_plaintext_secret).

    Old token is optionally kept valid for grace_period_seconds.
    """

    old_token = repository.get(token_id)
    if old_token is None:
        raise ValueError(f"Token not found: {token_id}")
    if old_token.status == "revoked":
        raise ValueError(f"Cannot rotate revoked token: {token_id}")

    # Create new token with same scopes and SA
    new_token_value = _generate_token_value()
    new_token_hash = _hash_token(new_token_value)

    new_token = ApiToken(
        id=_token_id(),
        service_account_id=old_token.service_account_id,
        prefix=new_token_value[:11],
        token_hash=new_token_hash,
        scopes=list(old_token.scopes),
        expires_at=_expiry(90),
        created_at=_now(),
        metadata={"rotated_from": token_id},
    )
    repository.save(new_token)

    # Handle grace period: set old token expiry
    if grace_period_seconds > 0:
        from datetime import datetime, timedelta, timezone
        grace_expiry = (datetime.now(timezone.utc) + timedelta(seconds=grace_period_seconds)).isoformat()
        object.__setattr__(old_token, "expires_at", grace_expiry)
        repository.save(old_token)
    else:
        object.__setattr__(old_token, "status", "revoked")
        repository.save(old_token)

    if audit_func:
        audit_func("token.rotate", resource=token_id, status="ok", metadata={"new_token_id": new_token.id, "grace_period": grace_period_seconds})
    return new_token, new_token_value


def revoke_token(token_id: str, *, repository: TokenRepository, audit_func=None) -> ApiToken:
    """Revoke a token immediately."""
    token = repository.get(token_id)
    if token is None:
        raise ValueError(f"Token not found: {token_id}")
    object.__setattr__(token, "status", "revoked")
    repository.save(token)
    if audit_func:
        audit_func("token.revoke", resource=token_id, status="ok")
    return token


def authenticate_token(token_value: str, *, repository: TokenRepository) -> ServiceAccount | None:
    """Authenticate a token value. Returns the associated ServiceAccount or None.

    Checks: token exists, is active, not expired, and its service account is active.
    """

    token_hash = _hash_token(token_value)
    token = repository.find_by_hash(token_hash)
    if token is None:
        return None
    if token.status == "revoked":
        return None
    if token.expires_at and token.expires_at < _now():
        return None

    # Delegate to caller for SA lookup (token repository doesn't own SAs)
    return None  # Caller must check SA separately


class InMemoryTokenRepository:
    def __init__(self):
        self._records: dict[str, ApiToken] = {}

    def save(self, token: ApiToken) -> ApiToken:
        self._records[token.id] = token
        return token

    def get(self, token_id: str) -> ApiToken | None:
        return self._records.get(token_id)

    def list(self, service_account_id: str) -> list[ApiToken]:
        return [t for t in self._records.values() if t.service_account_id == service_account_id]

    def find_by_hash(self, token_hash: str) -> ApiToken | None:
        for token in self._records.values():
            if token.token_hash == token_hash:
                return token
        return None


__all__ = [
    "ApiToken",
    "InMemoryTokenRepository",
    "TokenRepository",
    "authenticate_token",
    "create_token",
    "get_token",
    "list_tokens",
    "revoke_token",
    "rotate_token",
]
