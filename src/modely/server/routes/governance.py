"""Governance route adapters."""

from __future__ import annotations


def evaluate_policy(service, payload: dict) -> dict:
    """Evaluate policy through an injected governance service."""

    decision = service.evaluate_policy(payload)
    return decision.to_dict() if hasattr(decision, "to_dict") else dict(decision)


def submit_approval(service, payload: dict) -> dict:
    """Submit an approval request through an injected governance service."""

    approval = service.submit_approval(payload)
    return approval.to_dict() if hasattr(approval, "to_dict") else dict(approval)


def approve_request(service, request_id: str, payload: dict | None = None) -> dict:
    """Approve an existing approval request through an injected governance service.

    Delegates to ``service.approve(request_id, reviewer, reason)``.
    The *payload* dict may contain ``reviewer`` and ``reason`` keys.
    """

    payload = payload or {}
    reviewer = payload.get("reviewer")
    reason = payload.get("reason")
    approval = service.approve(request_id, reviewer=reviewer, reason=reason)
    return approval.to_dict() if hasattr(approval, "to_dict") else dict(approval)


def reject_request(service, request_id: str, payload: dict | None = None) -> dict:
    """Reject an existing approval request through an injected governance service.

    Delegates to ``service.reject(request_id, reviewer, reason)``.
    The *payload* dict may contain ``reviewer`` and ``reason`` keys.
    """

    payload = payload or {}
    reviewer = payload.get("reviewer")
    reason = payload.get("reason")
    approval = service.reject(request_id, reviewer=reviewer, reason=reason)
    return approval.to_dict() if hasattr(approval, "to_dict") else dict(approval)


def cancel_request(service, request_id: str) -> dict:
    """Cancel an existing approval request through an injected governance service.

    Delegates to ``service.cancel(request_id)``.
    """

    approval = service.cancel(request_id)
    return approval.to_dict() if hasattr(approval, "to_dict") else dict(approval)


def list_requests(service, filters: dict | None = None) -> dict:
    """List approval requests through an injected governance service.

    Delegates to ``service.list_requests(filters)``.
    The *filters* dict may contain ``status``, ``asset_id``, ``requester``,
    and other query parameters.
    """

    requests = service.list_requests(filters or {})
    return {
        "requests": [
            r.to_dict() if hasattr(r, "to_dict") else dict(r)
            for r in requests
        ],
        "total": len(requests),
    }


def get_request(service, request_id: str) -> dict:
    """Get a single approval request by id through an injected governance service.

    Delegates to ``service.get_request(request_id)``.
    """

    approval = service.get_request(request_id)
    return approval.to_dict() if hasattr(approval, "to_dict") else dict(approval)


__all__ = [
    "approve_request",
    "cancel_request",
    "create_service_account_route",
    "create_token_route",
    "disable_service_account_route",
    "evaluate_policy",
    "get_request",
    "get_service_account_route",
    "get_token_route",
    "list_requests",
    "list_service_accounts_route",
    "list_tokens_route",
    "reject_request",
    "revoke_token_route",
    "rotate_token_route",
    "submit_approval",
]


# -- Service Account & Token routes (Phase 3) ---------------------------------

def list_service_accounts_route(service, *, request_id: str = "req_unknown", **filters) -> dict:
    """GET /api/v1/service-accounts"""
    from modely.governance.service_accounts import list_service_accounts
    sas = list_service_accounts(tenant_scope=filters.get("tenant_scope"), repository=service._sa_repo if hasattr(service, "_sa_repo") else None)
    return {"data": {"service_accounts": [sa.to_dict() for sa in sas]}, "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def create_service_account_route(service, *, request_id: str = "req_unknown", **payload) -> dict:
    """POST /api/v1/service-accounts/create"""
    from modely.governance.service_accounts import InMemoryServiceAccountRepository, create_service_account
    repo = getattr(service, "_sa_repo", None) or InMemoryServiceAccountRepository()
    sa = create_service_account(name=payload.get("name", ""), owner_id=payload.get("owner_id", ""), tenant_scope=payload.get("tenant_scope", "default"), roles=payload.get("roles", ["Viewer"]), repository=repo)
    return {"data": sa.to_dict(), "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def get_service_account_route(service, sa_id: str, *, request_id: str = "req_unknown") -> dict:
    """GET /api/v1/service-accounts/{id}"""
    from modely.governance.service_accounts import InMemoryServiceAccountRepository, get_service_account
    repo = getattr(service, "_sa_repo", None) or InMemoryServiceAccountRepository()
    sa = get_service_account(sa_id, repository=repo)
    if sa is None:
        return {"error": {"code": "not_found", "message": f"Service account not found: {sa_id}", "request_id": request_id}}
    return {"data": sa.to_dict(), "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def disable_service_account_route(service, sa_id: str, *, request_id: str = "req_unknown") -> dict:
    """POST /api/v1/service-accounts/{id}/disable"""
    from modely.governance.service_accounts import InMemoryServiceAccountRepository, disable_service_account
    repo = getattr(service, "_sa_repo", None) or InMemoryServiceAccountRepository()
    sa = disable_service_account(sa_id, repository=repo)
    return {"data": sa.to_dict(), "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def create_token_route(service, sa_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    """POST /api/v1/service-accounts/{id}/tokens"""
    from modely.governance.api_tokens import InMemoryTokenRepository, create_token
    repo = getattr(service, "_token_repo", None) or InMemoryTokenRepository()
    token, secret = create_token(service_account_id=sa_id, scopes=payload.get("scopes", ["asset:read"]), expires_in_days=payload.get("expires_in_days", 90), repository=repo)
    result = token.to_dict()
    result["token"] = secret
    return {"data": result, "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def list_tokens_route(service, *, request_id: str = "req_unknown", **filters) -> dict:
    """GET /api/v1/api-tokens"""
    from modely.governance.api_tokens import InMemoryTokenRepository, list_tokens
    repo = getattr(service, "_token_repo", None) or InMemoryTokenRepository()
    tokens = list_tokens(filters.get("service_account_id", ""), repository=repo)
    return {"data": {"tokens": [t.to_dict() for t in tokens]}, "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def get_token_route(service, token_id: str, *, request_id: str = "req_unknown") -> dict:
    """GET /api/v1/api-tokens/{id}"""
    from modely.governance.api_tokens import InMemoryTokenRepository, get_token
    repo = getattr(service, "_token_repo", None) or InMemoryTokenRepository()
    token = get_token(token_id, repository=repo)
    if token is None:
        return {"error": {"code": "not_found", "message": f"Token not found: {token_id}", "request_id": request_id}}
    return {"data": token.to_dict(), "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def rotate_token_route(service, token_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    """POST /api/v1/api-tokens/{id}/rotate"""
    from modely.governance.api_tokens import InMemoryTokenRepository, rotate_token
    repo = getattr(service, "_token_repo", None) or InMemoryTokenRepository()
    new_token, new_secret = rotate_token(token_id, grace_period_seconds=payload.get("grace_period_seconds", 0), repository=repo)
    result = new_token.to_dict()
    result["token"] = new_secret
    return {"data": result, "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}


def revoke_token_route(service, token_id: str, *, request_id: str = "req_unknown") -> dict:
    """POST /api/v1/api-tokens/{id}/revoke"""
    from modely.governance.api_tokens import InMemoryTokenRepository, revoke_token
    repo = getattr(service, "_token_repo", None) or InMemoryTokenRepository()
    token = revoke_token(token_id, repository=repo)
    return {"data": token.to_dict(), "meta": {"request_id": request_id, "schema_version": "v1", "pagination": None}}
