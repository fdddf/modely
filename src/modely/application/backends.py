"""Backend capability registry."""

from __future__ import annotations

import json

from ..backend_registry import get_capability, list_capabilities
from ..types import BackendCapability


def list_backends() -> list[BackendCapability]:
    """List known backend capabilities."""
    return list_capabilities()


def get_backend_capabilities(name: str) -> BackendCapability:
    """Return capabilities for a backend name or alias."""
    return get_capability(name)


def print_backend_capabilities(items, *, as_json: bool = False) -> None:
    """Print one or more backend capability records."""
    if not isinstance(items, list):
        items = [items]
    if as_json:
        print(json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False))
        return

    headers = ["Backend", "Source", "Kind", "Status"]
    rows = []
    for item in items:
        status = "available" if item.available else "unavailable"
        if item.requires_extra:
            status = f"{status} (requires: {item.requires_extra})"
        rows.append([item.name, item.source, item.kind, status])

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    print("  ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for item, row in zip(items, rows):
        print("  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row)))
        supported = [k for k, v in item.supports.items() if v]
        print(f"  Supports: {', '.join(supported) if supported else '-'}")
        for note in item.notes:
            print(f"  Note:     {note}")
        print()
