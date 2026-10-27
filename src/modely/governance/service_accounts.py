"""Service account lifecycle services for Phase 3b.

Service accounts are machine principals that reuse Phase 2 RBAC roles and
permissions. They are bound to tenant/team/project and carry scoped roles.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


class ServiceAccountRepository(Protocol):
    """Backend-neutral repository for service accounts."""

    def save(self, sa: "ServiceAccount") -> "ServiceAccount": ...
    def get(self, sa_id: str) -> "ServiceAccount | None": ...
    def list(self, tenant_scope: str | None = None) -> list["ServiceAccount"]: ...
    def delete(self, sa_id: str) -> None: ...


@dataclass
class ServiceAccount:
    """A machine principal bound to a tenant/team/project with RBAC roles."""

    id: str
    name: str
    owner_id: str = ""
    tenant_scope: str = "default"
    team_id: str | None = None
    project_id: str | None = None
    roles: list[str] = field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sa_id() -> str:
    return f"sa_{uuid.uuid4().hex[:12]}"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def create_service_account(
    *,
    name: str,
    owner_id: str = "",
    tenant_scope: str = "default",
    team_id: str | None = None,
    project_id: str | None = None,
    roles: list[str] | None = None,
    repository: ServiceAccountRepository,
    audit_func=None,
) -> ServiceAccount:
    sa = ServiceAccount(
        id=_sa_id(), name=name, owner_id=owner_id, tenant_scope=tenant_scope,
        team_id=team_id, project_id=project_id, roles=roles or ["Viewer"],
        created_at=_now(), updated_at=_now(),
    )
    repository.save(sa)
    if audit_func:
        audit_func("service_account.create", resource=sa.id, status="ok", metadata={"name": name, "tenant_scope": tenant_scope})
    return sa


def get_service_account(sa_id: str, *, repository: ServiceAccountRepository) -> ServiceAccount | None:
    return repository.get(sa_id)


def list_service_accounts(*, tenant_scope: str | None = None, repository: ServiceAccountRepository) -> list[ServiceAccount]:
    return repository.list(tenant_scope=tenant_scope)


def update_service_account(sa_id: str, *, repository: ServiceAccountRepository, audit_func=None, **fields) -> ServiceAccount:
    sa = repository.get(sa_id)
    if sa is None:
        raise ValueError(f"Service account not found: {sa_id}")
    for key, value in fields.items():
        if hasattr(sa, key) and value is not None:
            object.__setattr__(sa, key, value)
    object.__setattr__(sa, "updated_at", _now())
    repository.save(sa)
    if audit_func:
        audit_func("service_account.update", resource=sa_id, status="ok", metadata={"fields": list(fields.keys())})
    return sa


def disable_service_account(sa_id: str, *, repository: ServiceAccountRepository, audit_func=None) -> ServiceAccount:
    sa = repository.get(sa_id)
    if sa is None:
        raise ValueError(f"Service account not found: {sa_id}")
    object.__setattr__(sa, "status", "disabled")
    object.__setattr__(sa, "updated_at", _now())
    repository.save(sa)
    if audit_func:
        audit_func("service_account.disable", resource=sa_id, status="ok")
    return sa


def transfer_owner(sa_id: str, new_owner_id: str, *, repository: ServiceAccountRepository, audit_func=None) -> ServiceAccount:
    sa = repository.get(sa_id)
    if sa is None:
        raise ValueError(f"Service account not found: {sa_id}")
    old_owner = sa.owner_id
    object.__setattr__(sa, "owner_id", new_owner_id)
    object.__setattr__(sa, "updated_at", _now())
    repository.save(sa)
    if audit_func:
        audit_func("service_account.transfer_owner", resource=sa_id, status="ok", metadata={"from": old_owner, "to": new_owner_id})
    return sa


class InMemoryServiceAccountRepository:
    def __init__(self):
        self._records: dict[str, ServiceAccount] = {}

    def save(self, sa: ServiceAccount) -> ServiceAccount:
        self._records[sa.id] = sa
        return sa

    def get(self, sa_id: str) -> ServiceAccount | None:
        return self._records.get(sa_id)

    def list(self, tenant_scope: str | None = None) -> list[ServiceAccount]:
        if tenant_scope:
            return [sa for sa in self._records.values() if sa.tenant_scope == tenant_scope]
        return list(self._records.values())

    def delete(self, sa_id: str) -> None:
        self._records.pop(sa_id, None)


__all__ = [
    "InMemoryServiceAccountRepository",
    "ServiceAccount",
    "ServiceAccountRepository",
    "create_service_account",
    "disable_service_account",
    "get_service_account",
    "list_service_accounts",
    "transfer_owner",
    "update_service_account",
]
