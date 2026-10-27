"""Phase 2 governance service — Approval workflow and quota enforcement.

Implements the complete approval request lifecycle (submit/approve/reject/cancel/list/get)
and quota enforcement hooks, binding them to existing Phase 2 primitives.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from ..governance.approvals import ApprovalRequest
from ..governance.audit import record_audit_event


# -- Repository Protocols ------------------------------------------------------


class ApprovalRepository(Protocol):
    def save(self, request: ApprovalRequest) -> ApprovalRequest: ...
    def get(self, request_id: str) -> ApprovalRequest | None: ...
    def list(self, **filters) -> list[ApprovalRequest]: ...


class InMemoryApprovalRepository:
    def __init__(self):
        self._records: dict[str, ApprovalRequest] = {}

    def save(self, request: ApprovalRequest) -> ApprovalRequest:
        self._records[request.id] = request
        return request

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._records.get(request_id)

    def list(self, **filters) -> list[ApprovalRequest]:
        results = list(self._records.values())
        if state := filters.get("state", filters.get("status")):
            results = [r for r in results if r.state == state]
        if asset_id := filters.get("asset_id"):
            results = [r for r in results if r.asset_id == asset_id]
        if requester := filters.get("requester"):
            results = [r for r in results if r.requester_principal == requester]
        return results


class QuotaRepository(Protocol):
    def get(self, subject: str, dimension: str) -> dict | None: ...
    def set(self, subject: str, dimension: str, limit: int, mode: str) -> dict: ...
    def delete(self, quota_id: str) -> None: ...
    def list(self, **filters) -> list[dict]: ...


class InMemoryQuotaRepository:
    def __init__(self):
        self._records: dict[str, dict] = {}

    def get(self, subject: str, dimension: str) -> dict | None:
        return self._records.get(f"{subject}:{dimension}")

    def set(self, subject: str, dimension: str, limit: int, mode: str = "soft") -> dict:
        key = f"{subject}:{dimension}"
        if key in self._records:
            entry = self._records[key]
            entry["limit"] = limit
            entry["mode"] = mode
        else:
            entry = {"id": key, "subject": subject, "dimension": dimension, "limit": limit, "mode": mode, "usage": 0}
            self._records[key] = entry
        return entry

    def delete(self, quota_id: str) -> None:
        self._records.pop(quota_id, None)

    def list(self, **filters) -> list[dict]:
        results = list(self._records.values())
        if subject := filters.get("subject"):
            results = [r for r in results if r["subject"] == subject]
        if dimension := filters.get("dimension"):
            results = [r for r in results if r["dimension"] == dimension]
        return results


# -- Governance Service --------------------------------------------------------


class GovernanceService:
    """Complete Phase 2 governance service: approval workflow + quota enforcement."""

    def __init__(self, *, approval_repo: ApprovalRepository | None = None, quota_repo: QuotaRepository | None = None):
        self._approval_repo = approval_repo or InMemoryApprovalRepository()
        self._quota_repo = quota_repo or InMemoryQuotaRepository()

    # -- Approval workflow ------------------------------------------------------

    def submit_approval(self, payload: dict) -> ApprovalRequest:
        request = ApprovalRequest(
            id=f"apr_{uuid.uuid4().hex[:12]}",
            asset_id=payload.get("asset_id", ""),
            requester_principal=payload.get("requester", ""),
            state="none",
            reason=payload.get("reason"),
            requested_actions=payload.get("requested_actions", []),
        )
        # Need to import the transition function from governance module
        from ..governance.approvals import transition_request as _transition
        submitted = _transition(request, "pending")
        self._approval_repo.save(submitted)
        record_audit_event("approval.submit", resource=submitted.id, status="ok",
                           metadata={"asset_id": submitted.asset_id, "requester": submitted.requester_principal})
        return submitted

    def approve(self, request_id: str, *, reviewer: str = "", reason: str = "") -> ApprovalRequest:
        request = self._approval_repo.get(request_id)
        if request is None:
            raise ValueError(f"Approval request not found: {request_id}")
        from ..governance.approvals import transition_request as _transition
        approved = _transition(request, "approved")
        approved.decision_by = reviewer
        approved.decision_reason = reason
        approved.decision_at = _now_iso()
        self._approval_repo.save(approved)
        record_audit_event("approval.approve", resource=request_id, status="ok", metadata={"reviewer": reviewer})
        return approved

    def reject(self, request_id: str, *, reviewer: str = "", reason: str = "") -> ApprovalRequest:
        request = self._approval_repo.get(request_id)
        if request is None:
            raise ValueError(f"Approval request not found: {request_id}")
        from ..governance.approvals import transition_request as _transition
        rejected = _transition(request, "rejected")
        rejected.decision_by = reviewer
        rejected.decision_reason = reason
        rejected.decision_at = _now_iso()
        self._approval_repo.save(rejected)
        record_audit_event("approval.reject", resource=request_id, status="ok", metadata={"reviewer": reviewer})
        return rejected

    def cancel(self, request_id: str) -> ApprovalRequest:
        request = self._approval_repo.get(request_id)
        if request is None:
            raise ValueError(f"Approval request not found: {request_id}")
        from ..governance.approvals import transition_request as _transition
        cancelled = _transition(request, "cancelled")
        self._approval_repo.save(cancelled)
        record_audit_event("approval.cancel", resource=request_id, status="ok")
        return cancelled

    def list_requests(self, filters: dict | None = None) -> list[ApprovalRequest]:
        return self._approval_repo.list(**(filters or {}))

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        return self._approval_repo.get(request_id)

    def evaluate_policy(self, payload: dict) -> dict:
        from ..governance.policy_engine import PolicyDecision
        outcome = payload.get("outcome", "warn")
        reasons = payload.get("reasons", [])
        risk_level = payload.get("risk_level", "unknown")
        return PolicyDecision(outcome=outcome, reasons=reasons, risk_level=risk_level)

    # -- Quota enforcement ------------------------------------------------------

    def list_quotas(self, subject: str = "", dimension: str = "", mode: str = "") -> list[dict]:
        filters = {}
        if subject: filters["subject"] = subject
        if dimension: filters["dimension"] = dimension
        return self._quota_repo.list(**filters)

    def get_quota(self, quota_id: str) -> dict:
        for r in self._quota_repo.list():
            if r["id"] == quota_id:
                return r
        raise ValueError(f"Quota not found: {quota_id}")

    def set_quota(self, payload: dict) -> dict:
        subject = payload.get("subject", "")
        dimension = payload.get("dimension", "")
        limit = payload.get("limit", 0)
        mode = payload.get("mode", "soft")
        return self._quota_repo.set(subject, dimension, limit, mode)

    def delete_quota(self, quota_id: str) -> None:
        self._quota_repo.delete(quota_id)

    def check_quota(self, subject: str, dimension: str) -> dict:
        """Check if a quota allows an operation. Returns {'allowed': True/False, ...}."""
        q = self._quota_repo.get(subject, dimension)
        if q is None:
            return {"allowed": True, "reason": "no_quota_set"}
        allowed = q["usage"] < q["limit"] or q["mode"] == "soft"
        return {"allowed": allowed, "limit": q["limit"], "usage": q["usage"], "mode": q["mode"],
                "reason": "ok" if allowed else f"Quota exceeded: {q['dimension']} limit {q['limit']}"}

    def record_usage(self, subject: str, dimension: str, amount: int = 1) -> dict:
        key = f"{subject}:{dimension}"
        q = self._quota_repo._records.get(key)
        if q is None: return {"allowed": True}
        q["usage"] += amount
        return {"allowed": q["usage"] <= q["limit"] or q.get("mode") == "soft", "usage": q["usage"], "limit": q["limit"]}

    # -- Credential management --------------------------------------------------

    def list_credentials(self, source: str = "", tenant_scope: str = "") -> list:
        return []

    def get_credential(self, credential_id: str):
        raise ValueError(f"Credential not found: {credential_id}")

    def register_credential(self, payload: dict):
        from ..syncing.adapters import SourceCredentialRef
        return SourceCredentialRef(ref=f"cred_{uuid.uuid4().hex[:8]}", provider=payload.get("source", ""), scope=payload.get("tenant_scope", ""))

    def revoke_credential(self, credential_id: str):
        return self.get_credential(credential_id)

    def list_audit_events(self, **filters) -> list:
        from ..governance.audit import list_audit_events as _list
        return _list(**{k: v for k, v in filters.items() if v})


__all__ = [
    "ApprovalRepository",
    "GovernanceService",
    "InMemoryApprovalRepository",
    "InMemoryQuotaRepository",
    "QuotaRepository",
]


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
