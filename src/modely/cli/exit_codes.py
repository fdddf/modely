"""Shared CLI exit codes for the modely enterprise CLI.

Maps to the stable exit code table defined in ``docs/specs/enterprise-cli.md``.
Every CLI handler that needs to signal an outcome to a calling script or CI
pipeline MUST import from this module rather than using bare integers.
"""

from __future__ import annotations

# Generic / transport
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

# Governance / policy
EXIT_POLICY_WARN = 10
EXIT_APPROVAL_REQUIRED = 11
EXIT_POLICY_BLOCKED = 12
EXIT_CHECKSUM_MISMATCH = 13

# Auth / access
EXIT_AUTH_DENIED = 14
EXIT_QUOTA_LIMITED = 15

__all__ = [
    "EXIT_SUCCESS",
    "EXIT_ERROR",
    "EXIT_USAGE",
    "EXIT_POLICY_WARN",
    "EXIT_APPROVAL_REQUIRED",
    "EXIT_POLICY_BLOCKED",
    "EXIT_CHECKSUM_MISMATCH",
    "EXIT_AUTH_DENIED",
    "EXIT_QUOTA_LIMITED",
]
