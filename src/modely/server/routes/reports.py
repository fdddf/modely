"""Report route adapters."""

from __future__ import annotations


def create_report(service, payload: dict) -> dict:
    """Create a report through an injected report service."""

    report = service.create_report(payload)
    return report.to_dict() if hasattr(report, "to_dict") else dict(report)


__all__ = ["create_report"]
