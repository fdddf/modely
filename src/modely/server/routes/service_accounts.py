"""Service Account & Token API route adapters.

Wraps the governance module's real service account and token lifecycle
services with the API envelope expected by the web frontend.
"""

from __future__ import annotations

from ..schemas.envelopes import success_response


# -- Service Accounts -----------------------------------------------------------

def list_service_accounts(service, *, request_id: str = "req_unknown", **query_params: str) -> dict:
    from modely.governance.service_accounts import InMemoryServiceAccountRepository, list_service_accounts as _list
    repo = getattr(service, "_sa_repo", None) or InMemoryServiceAccountRepository()
    sas = _list(repository=repo)
    return success_response(
        {"service_accounts": [sa.to_dict() for sa in sas], "total": len(sas)},
        request_id=request_id,
    )


def create_service_account(service, *, request_id: str = "req_unknown", **payload) -> dict:
    from modely.governance.service_accounts import InMemoryServiceAccountRepository, create_service_account as _create
    repo = getattr(service, "_sa_repo", None) or InMemoryServiceAccountRepository()
    sa = _create(
        name=payload.get("name", ""),
        owner_id=payload.get("owner_id", payload.get("owner", "")),
        tenant_scope=payload.get("tenant_scope", "default"),
        roles=payload.get("roles", ["Viewer"]),
        repository=repo,
    )
    return success_response(sa.to_dict(), request_id=request_id)


def get_service_account(service, sa_id: str, *, request_id: str = "req_unknown") -> dict:
    from modely.governance.service_accounts import InMemoryServiceAccountRepository, get_service_account as _get
    repo = getattr(service, "_sa_repo", None) or InMemoryServiceAccountRepository()
    sa = _get(sa_id, repository=repo)
    if sa is None:
        from ..schemas.envelopes import error_response
        return error_response("not_found", f"Service account not found: {sa_id}", request_id=request_id)
    return success_response(sa.to_dict(), request_id=request_id)


# -- Tokens ---------------------------------------------------------------------

def create_token_for_sa(service, sa_id: str, *, request_id: str = "req_unknown", **payload) -> dict:
    from modely.governance.api_tokens import InMemoryTokenRepository, create_token as _create_token
    repo = getattr(service, "_token_repo", None) or InMemoryTokenRepository()
    scopes = payload.get("scopes", ["asset:read"])
    expires_in_days = int(payload.get("expires_in_days", 90))
    token, secret = _create_token(
        service_account_id=sa_id,
        scopes=scopes if isinstance(scopes, list) else [s.strip() for s in str(scopes).split(",")],
        expires_in_days=expires_in_days,
        repository=repo,
    )
    result = token.to_dict()
    result["token"] = secret  # plaintext secret shown only once
    return success_response(result, request_id=request_id)


__all__ = ["create_service_account", "create_token_for_sa", "get_service_account", "list_service_accounts"]
