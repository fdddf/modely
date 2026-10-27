"""Shared API response and error envelope helpers.

Implements the canonical envelope shapes defined in docs/specs/enterprise-api.md:

    Success:
        {"data": {}, "meta": {"request_id": "req_...", "schema_version": "v1", "pagination": null}}

    Error:
        {"error": {"code": "...", "message": "...", "details": {}, "request_id": "req_..."}}
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


# Stable error codes from docs/specs/enterprise-api.md.
STABLE_ERROR_CODES: set[str] = {
    "auth_required",
    "permission_denied",
    "policy_blocked",
    "approval_required",
    "manifest_mismatch",
    "checksum_mismatch",
    "quota_limited",
    "validation_error",
    "not_found",
    "conflict_idempotency",
    "upstream_unavailable",
    "internal_error",
}


def generate_request_id() -> str:
    """Return a request/correlation id with the canonical ``req_`` prefix."""
    return f"req_{uuid.uuid4().hex[:16]}"


@dataclass
class Pagination:
    """Pagination metadata for list endpoints."""

    total: int
    page: int
    page_size: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResponseMeta:
    """Metadata wrapper for every API success response."""

    request_id: str
    schema_version: str = "v1"
    pagination: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"request_id": self.request_id, "schema_version": self.schema_version}
        payload["pagination"] = self.pagination.to_dict() if isinstance(self.pagination, Pagination) else self.pagination
        return payload


@dataclass
class ErrorDetail:
    """Stable error payload for every API error response."""

    code: str
    message: str
    request_id: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details, "request_id": self.request_id}


@dataclass
class Principal:
    """Dev/basic auth principal used for Phase 1 placeholder auth."""

    id: str
    role: str  # admin, developer, viewer
    labels: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Factory helpers ---------------------------------------------------------


def success_response(
    data: Any,
    request_id: str,
    *,
    pagination: Pagination | None = None,
    schema_version: str = "v1",
) -> dict[str, Any]:
    """Build a canonical success response envelope."""
    return {
        "data": data,
        "meta": ResponseMeta(request_id=request_id, schema_version=schema_version, pagination=pagination).to_dict(),
    }


def error_response(
    code: str,
    message: str,
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical error response envelope."""
    return {
        "error": ErrorDetail(code=code, message=message, request_id=request_id, details=details or {}).to_dict(),
    }


__all__ = [
    "ErrorDetail",
    "Pagination",
    "Principal",
    "ResponseMeta",
    "STABLE_ERROR_CODES",
    "error_response",
    "generate_request_id",
    "success_response",
]
