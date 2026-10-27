"""Request and response schemas for the enterprise server.

This module is part of the enterprise platform package skeleton. It intentionally contains no implementation yet; add behavior through the phase-specific task plans under tasks/enterprise-platform/.
"""

from __future__ import annotations

from .envelopes import (
    ErrorDetail,
    Pagination,
    Principal,
    ResponseMeta,
    STABLE_ERROR_CODES,
    error_response,
    generate_request_id,
    success_response,
)

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
