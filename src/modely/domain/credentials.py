"""Source credential domain object.

Source credentials are separate from Phase 3 service-account/API tokens.
They grant modely-ai access to upstream or internal sources during sync/import.

IMPORTANT: Secrets are never returned after creation.  Only metadata and
redacted token prefixes are shown.  Logs, reports, audit payloads, and errors
must show only redacted metadata.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


_REDACTED_MARKER = "***REDACTED***"


def _redact(value: str | None) -> str | None:
    """Redact a secret value, showing only the prefix length."""
    if value is None:
        return None
    return _REDACTED_MARKER


@dataclass
class SourceCredential:
    """A credential granting modely-ai access to an external or internal source.

    ``secret_ref`` holds the raw credential (token, PAT, key pair, etc.) during
    construction but is redacted in ``to_dict()`` and ``repr()``.  Workers may
    only request source credentials through tenant-scoped credential resolution.
    """

    id: str
    tenant_scope: str  # e.g. "org:workspace"
    source: str  # huggingface, modelscope, kaggle, github, gitlab, s3, minio, custom
    credential_type: str  # bearer_token, username_password, pat, access_key_pair, oauth_app, custom
    owner: str = ""  # owning principal id (e.g. user:u1, team:t1)
    secret_ref: str | None = None
    owner_principal: str | None = None  # deprecated — use `owner`
    owner_team: str | None = None  # deprecated — use `owner`
    allowed_actions: list[str] = field(default_factory=list)
    created_at: str | None = None
    rotated_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Backfill `owner` from deprecated fields if not explicitly set."""
        if not self.owner and self.owner_principal:
            self.owner = self.owner_principal
        elif not self.owner and self.owner_team:
            self.owner = self.owner_team

    def to_dict(self):
        d = asdict(self)
        d["secret_ref"] = _redact(self.secret_ref)
        return d

    def to_safe_dict(self) -> dict:
        """Return a dict safe for audit/log/render contexts (no secret_ref)."""
        d = self.to_dict()
        d.pop("secret_ref", None)
        return d

    def __repr__(self) -> str:
        """Redacted repr — never leaks the raw credential value."""
        safe = {
            "id": self.id,
            "tenant_scope": self.tenant_scope,
            "source": self.source,
            "credential_type": self.credential_type,
            "owner": self.owner,
            "cred_ref": _redact(self.secret_ref),
            "allowed_actions": self.allowed_actions,
            "created_at": self.created_at,
            "rotated_at": self.rotated_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "last_used_at": self.last_used_at,
            "metadata": self.metadata,
        }
        return (
            f"{self.__class__.__name__}("
            + ", ".join(f"{k}={v!r}" for k, v in safe.items())
            + ")"
        )


__all__ = ["SourceCredential"]
