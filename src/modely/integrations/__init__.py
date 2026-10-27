"""Enterprise platform integration adapter contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class IntegrationCapability:
    """Capability declaration for an enterprise integration adapter."""

    name: str
    available: bool = False
    supports: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IntegrationAdapter(Protocol):
    """Minimal protocol implemented by future integration adapters."""

    capability: IntegrationCapability

    def health(self) -> dict[str, Any]: ...


def planned_capability(name: str, *notes: str) -> IntegrationCapability:
    """Return a not-yet-implemented integration capability descriptor."""

    return IntegrationCapability(name=name, available=False, notes=list(notes or ["planned integration adapter"]))


__all__ = ["IntegrationAdapter", "IntegrationCapability", "planned_capability"]
