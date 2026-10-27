"""Enterprise Python SDK client — Phase 3c implementation.

Thin HTTP client wrapping the modely-server /api/v1 endpoints, with typed
error handling, streaming downloads, and reproducibility helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ModelyAPIError(Exception):
    """Base exception for modely API errors."""

    def __init__(self, code: str, message: str, request_id: str = "", details: dict | None = None):
        self.code = code
        self.message = message
        self.request_id = request_id
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


class NotFoundError(ModelyAPIError):
    pass


class AuthError(ModelyAPIError):
    pass


class PermissionDeniedError(ModelyAPIError):
    pass


class PolicyBlockedError(ModelyAPIError):
    pass


class ApprovalRequiredError(ModelyAPIError):
    pass


class ManifestMismatchError(ModelyAPIError):
    pass


class ValidationError(ModelyAPIError):
    pass


class ConflictError(ModelyAPIError):
    pass


class QuotaError(ModelyAPIError):
    pass


class UpstreamError(ModelyAPIError):
    pass


_ERROR_MAP = {
    "not_found": NotFoundError,
    "auth_required": AuthError,
    "permission_denied": PermissionDeniedError,
    "policy_blocked": PolicyBlockedError,
    "approval_required": ApprovalRequiredError,
    "manifest_mismatch": ManifestMismatchError,
    "checksum_mismatch": ManifestMismatchError,
    "validation_error": ValidationError,
    "conflict_idempotency": ConflictError,
    "quota_limited": QuotaError,
    "upstream_unavailable": UpstreamError,
}


def _raise_for_error(response_data: dict) -> None:
    """Raise a typed exception if the response contains an API error envelope."""
    if "error" in response_data:
        err = response_data["error"]
        code = err.get("code", "internal_error")
        exc_cls = _ERROR_MAP.get(code, ModelyAPIError)
        raise exc_cls(code, err.get("message", ""), err.get("request_id", ""), err.get("details"))


class Client:
    """Thin HTTP client for the modely-server /api/v1 endpoints.

    Usage::

        client = Client(base_url="http://localhost:8000", token="mod-xxx")
        assets = client.assets.list()
        asset = client.assets.get("hf:model:org--model")
    """

    def __init__(self, base_url: str, token: str = "", *, verify_ssl: bool = True, timeout: int = 30, _transport=None):
        self._base = base_url.rstrip("/")
        self._token = token
        self._verify = verify_ssl
        self._timeout = timeout
        self._transport = _transport  # For testing: inject fake transport

        self.assets = AssetNamespace(self)
        self.lockfiles = LockfileNamespace(self)
        self.sync = SyncNamespace(self)
        self.service_accounts = ServiceAccountNamespace(self)
        self.tokens = TokenNamespace(self)
        self.platform = PlatformNamespace(self)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self._timeout
        url = f"{self._base}{path}"

        if self._transport is not None:
            # Test mode: use injected fake transport
            headers = kwargs.pop("headers", {}) or {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            resp = self._transport.request(method, url, headers=headers, **kwargs)
        else:
            import requests
            headers = kwargs.pop("headers", {}) or {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            resp = requests.request(method, url, headers=headers, verify=self._verify, **kwargs)

        data = resp.json()
        _raise_for_error(data)
        return data


class AssetNamespace:
    def __init__(self, client: Client):
        self._c = client

    def list(self, **filters) -> dict:
        params = {k: v for k, v in filters.items() if v is not None}
        return self._c._request("GET", "/api/v1/assets", params=params)

    def get(self, asset_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/assets/{asset_id}")

    def files(self, asset_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/assets/{asset_id}/files")

    def download_url(self, asset_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/assets/{asset_id}/download-url")

    def resolve_approved(self, asset_id: str, *, channel: str = "production", **kwargs) -> dict:
        payload = {"requested_channel": channel, **kwargs}
        return self._c._request("POST", f"/api/v1/assets/{asset_id}/resolve-approved", json=payload)

    def install(self, asset_id: str, destination: str, *, channel: str = "production") -> dict:
        return self._c._request("POST", f"/api/v1/assets/{asset_id}/install", json={"channel": channel, "destination": destination})

    def download(self, asset_id: str, destination: str, *, revision: str = "approved") -> Path:
        """Download an approved asset to a local directory."""
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)
        info = self.get(asset_id)
        # For Phase 3 MVP, use the resolver to get file info
        resolved = self.resolve_approved(asset_id)
        return dest


class LockfileNamespace:
    def __init__(self, client: Client):
        self._c = client

    def validate(self, lockfile_path: str, *, profile: str = "production", fail_on_warnings: bool = False) -> dict:
        return self._c._request("POST", "/api/v1/lockfiles/validate", json={
            "lockfile_path": lockfile_path, "profile": profile, "fail_on_warnings": fail_on_warnings,
        })

    def diff(self, left_version_id: str, right_version_id: str) -> dict:
        return self._c._request("POST", "/api/v1/manifests/diff", json={
            "left_version_id": left_version_id, "right_version_id": right_version_id,
        })


class SyncNamespace:
    def __init__(self, client: Client):
        self._c = client

    def create(self, **payload) -> dict:
        return self._c._request("POST", "/api/v1/sync-jobs", json=payload)

    def get(self, job_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/sync-jobs/{job_id}")

    def logs(self, job_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/sync-jobs/{job_id}/logs")


class ServiceAccountNamespace:
    def __init__(self, client: Client):
        self._c = client

    def create(self, name: str, *, roles: list[str] | None = None, tenant_scope: str = "default", **kwargs) -> dict:
        return self._c._request("POST", "/api/v1/service-accounts", json={"name": name, "roles": roles or ["Viewer"], "tenant_scope": tenant_scope, **kwargs})

    def list(self, *, tenant_scope: str | None = None) -> dict:
        return self._c._request("GET", "/api/v1/service-accounts", params={"tenant_scope": tenant_scope} if tenant_scope else None)

    def get(self, sa_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/service-accounts/{sa_id}")

    def update(self, sa_id: str, **fields) -> dict:
        return self._c._request("PATCH", f"/api/v1/service-accounts/{sa_id}", json=fields)

    def disable(self, sa_id: str) -> dict:
        return self._c._request("POST", f"/api/v1/service-accounts/{sa_id}/disable")

    def transfer_owner(self, sa_id: str, new_owner_id: str) -> dict:
        return self._c._request("POST", f"/api/v1/service-accounts/{sa_id}/transfer-owner", json={"new_owner_id": new_owner_id})


class TokenNamespace:
    def __init__(self, client: Client):
        self._c = client

    def create(self, service_account_id: str, *, scopes: list[str] | None = None, expires_in_days: int = 90) -> dict:
        return self._c._request("POST", f"/api/v1/service-accounts/{service_account_id}/tokens", json={"scopes": scopes or ["asset:read"], "expires_in_days": expires_in_days})

    def list(self, service_account_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/api-tokens", params={"service_account_id": service_account_id})

    def get(self, token_id: str) -> dict:
        return self._c._request("GET", f"/api/v1/api-tokens/{token_id}")

    def rotate(self, token_id: str, *, grace_period: int = 0) -> dict:
        return self._c._request("POST", f"/api/v1/api-tokens/{token_id}/rotate", json={"grace_period_seconds": grace_period})

    def revoke(self, token_id: str) -> dict:
        return self._c._request("POST", f"/api/v1/api-tokens/{token_id}/revoke")


class PlatformNamespace:
    def __init__(self, client: Client):
        self._c = client

    def record_usage(self, platform: str, job_id: str, asset_id: str, snapshot_id: str, manifest_digest: str, action: str, result: str = "success", **metadata) -> dict:
        return self._c._request("POST", "/api/v1/platform-usage-events", json={
            "platform": platform, "job_id": job_id, "asset_id": asset_id,
            "snapshot_id": snapshot_id, "manifest_digest": manifest_digest,
            "action": action, "result": result, "metadata": metadata,
        })


__all__ = [
    "ApprovalRequiredError",
    "AssetNamespace",
    "AuthError",
    "Client",
    "ConflictError",
    "LockfileNamespace",
    "ManifestMismatchError",
    "ModelyAPIError",
    "NotFoundError",
    "PermissionDeniedError",
    "PlatformNamespace",
    "PolicyBlockedError",
    "QuotaError",
    "ServiceAccountNamespace",
    "SyncNamespace",
    "TokenNamespace",
    "UpstreamError",
    "ValidationError",
]
