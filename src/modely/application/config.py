"""Application-level configuration and secret separation notes.

Design decisions and integration points for keeping configuration and secrets
separate in the enterprise platform.

Config vs. Secrets
------------------

**Configuration** (stored in environment variables, config files, or a
configuration service):

- server host/port
- log levels and output targets
- feature flags
- cache directory paths
- default policy profiles
- catalog backend configuration
- notification channel settings
- SLA timers and approval expiry defaults

**Secrets** (stored in environment variables, secrets managers, or vaults;
never in config files checked into source control):

- source credentials (``SourceCredential.secret_ref``)
- OIDC/LDAP client secrets
- API tokens for external platforms (HF, ModelScope, Kaggle, GitHub, GitLab)
- S3/MinIO access keys
- database connection strings (if applicable)
- signing keys for JWT tokens
- encryption keys for at-rest data

Integration Points
------------------

1. **Config loading**: Use ``os.environ.get`` with sensible defaults.
   Never read secrets from a flat config file without encryption.

2. **Secret resolution (Phase 3)**: Service accounts and API tokens must be
   resolved through the governance token registry (``governance/token_registry.py``
   when implemented), not through flat environment variables.

3. **Credential resolution (Phase 2)**: ``domain.credentials.SourceCredential``
   holds the credential metadata; ``secret_ref`` is the reference to the actual
   secret (never the secret itself after construction).  Workers should
   resolve credentials through a tenant-scoped credential resolver interface
   (not yet implemented).

4. **Config validation**: All config values used by the server or application
   layer should be validated at startup (type checks, range checks,
   required-field checks) via a ``validate_config`` function.

5. **Secret lifecycle**: Secrets have creation, rotation, and expiry dates
   (``created_at``, ``rotated_at``, ``expires_at``).  A background task
   should warn when secrets are close to expiry and rotate them if supported
   by the source.

6. **Audit boundary**: Any operation that reads or uses a secret must record
   an audit event (``domain.audit_events.AUDIT_TOKEN_ISSUED``,
   ``AUDIT_TOKEN_ROTATED``, ``AUDIT_TOKEN_REVOKED``) without including the
   secret value in the audit payload.  Use
   ``governance.redaction.redact_credential_metadata`` to produce safe audit
   payloads.

7. **Environment variable convention**: All modely config env vars use the
   ``MODELY_`` prefix.  Secrets use platform-specific prefixes
   (``HF_TOKEN``, ``MODELSCOPE_TOKEN``, ``GITHUB_TOKEN``, ``KAGGLE_KEY``)
   as established by the existing ``modely.auth`` module.

Phase Roadmap
-------------

- **Phase 1 (current)**: Flat environment variables plus ``~/.modely/config.json``
  with ``chmod 600`` best-effort protection.
- **Phase 2**: ``SourceCredential`` domain object with redacted serialization;
  governance/redaction helpers for credential metadata in audit logs and reports.
- **Phase 3**: Dedicated secret manager integration (AWS Secrets Manager,
  HashiCorp Vault, or environment-specific provider); service-account token
  registry with rotation and revocation.
- **Phase 4**: Automated secret rotation with zero-downtime credential
  handoff; at-rest encryption for all stored credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Any


# Keys that config readers strip as known-secret patterns
_CONFIG_SECRET_KEY_PATTERNS = (
    "token",
    "password",
    "secret",
    "api_key",
    "access_key",
    "private_key",
)


@dataclass
class Settings:
    """Non-secret application settings.

    All secret values (API tokens, passwords, keys) are stored externally
    and resolved at runtime via credential resolution.
    """

    # -- Cache ----------------------------------------------------------------
    cache_dir: str = ""
    cache_ttl_hours: int = 24

    # -- Server ---------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # -- Governance defaults --------------------------------------------------
    default_policy_profile: str = ""
    default_quota_mode: str = "advisory"
    approval_sla_hours: int = 24

    # -- Sync defaults --------------------------------------------------------
    max_concurrent_sync_jobs: int = 5
    sync_retry_max: int = 3
    sync_timeout_seconds: int = 3600

    # -- Mirror ---------------------------------------------------------------
    mirror_url: str = ""
    mirror_cache_dir: str = ""

    # -- Feature flags --------------------------------------------------------
    enable_catalog: bool = True
    enable_sync: bool = True
    enable_governance: bool = True
    enable_reporting: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Export settings as dict (safe for logging, no secrets)."""
        result: dict[str, Any] = {}
        for f in fields(self):
            if not _is_secret_key(f.name):
                result[f.name] = getattr(self, f.name)
        return result


def _is_secret_key(name: str) -> bool:
    """Check whether a config key name matches known secret patterns."""
    lowered = name.lower()
    return any(pattern in lowered for pattern in _CONFIG_SECRET_KEY_PATTERNS)


def strip_secrets(config: dict[str, Any]) -> dict[str, Any]:
    """Strip any known-secret keys from a config dict.

    Use before logging, reporting, or exposing configuration.
    """
    safe: dict[str, Any] = {}
    for key, value in config.items():
        if _is_secret_key(key):
            safe[key] = "<stripped>"
        elif isinstance(value, dict):
            safe[key] = strip_secrets(value)
        elif isinstance(value, list):
            safe[key] = [
                strip_secrets(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            safe[key] = value
    return safe


def load_config_from_env(prefix: str = "MODELY_") -> dict[str, Any]:
    """Load configuration from environment variables with a given prefix.

    Returns a dict with stripped prefix and lowercased keys.  Secret keys are
    automatically stripped (replaced with ``<stripped>``).
    """
    config: dict[str, Any] = {}
    for key, value in sorted(os.environ.items()):
        if key.startswith(prefix):
            config_key = key[len(prefix):].lower()
            config[config_key] = value
    return strip_secrets(config)


def validate_config(cfg: dict[str, Any]) -> list[str]:
    """Validate a configuration dict and return a list of error messages.

    Extend this as new configuration keys are added.
    """
    errors: list[str] = []
    # Example checks (expand as config surface grows):
    if "server_port" in cfg:
        port = cfg["server_port"]
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append(f"server_port must be an integer 1-65535, got {port!r}")
    return errors


__all__ = [
    "Settings",
    "load_config_from_env",
    "strip_secrets",
    "validate_config",
]
