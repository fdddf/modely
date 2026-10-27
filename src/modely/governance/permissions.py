"""Permission evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

DEFAULT_ACTIONS = {
    "asset:read",
    "asset:download",
    "asset:sync",
    "asset:publish",
    "asset:approve",
    "asset:delete",
    "asset:scan",
    "asset:manage_acl",
    "report:read",
    "policy:manage",
    "audit:read",
    "token:manage",
}


@dataclass
class PermissionDecision:
    """Result of evaluating one permission action."""

    allowed: bool
    action: str
    reason: str = ""
    metadata: dict = field(default_factory=dict)


def allow(action: str, *, allowed_actions=None) -> PermissionDecision:
    """Evaluate an action against an allowed action set."""
    allowed_actions = set(DEFAULT_ACTIONS if allowed_actions is None else allowed_actions)
    return PermissionDecision(action in allowed_actions, action, "allowed" if action in allowed_actions else "denied")


def batch_check_permissions(
    principal_actions,
    actions: list[str] | None = None,
    *,
    allowed_actions_set: set | None = None,
) -> dict[str, PermissionDecision] | list:
    """Evaluate multiple (principal, action) pairs in one batch.

    Supports two calling conventions:

    - ``batch_check_permissions(pairs)`` where *pairs* is a sequence of
      ``(principal, action)`` tuples.  Returns a ``list`` of
      ``PermissionDecision`` in the same order.
    - ``batch_check_permissions(principal, actions)`` for checking many
      actions against a single principal.  Returns a ``dict`` mapping each
      action string to its ``PermissionDecision``.

    When *allowed_actions_set* is provided, roles are bypassed and the
    explicit set is used directly (useful for testing or static ACLs).
    """

    from .rbac import check_permission

    # Detect calling convention: if actions is provided, it is the
    # (principal, list-of-actions) form.  Otherwise principal_actions
    # is a sequence of (principal, action) tuples.
    if actions is not None:
        # Single principal + list of actions
        results: dict[str, PermissionDecision] = {}
        principal = principal_actions
        for action in actions:
            if allowed_actions_set is not None:
                decision = allow(action, allowed_actions=allowed_actions_set)
                decision.metadata["principal_id"] = getattr(principal, "id", "")
            else:
                decision = check_permission(principal, action)
            results[action] = decision
        return results

    # Sequence of (principal, action) tuples
    results: list = []
    for principal, action in principal_actions:
        if allowed_actions_set is not None:
            decision = allow(action, allowed_actions=allowed_actions_set)
            decision.metadata["principal_id"] = getattr(principal, "id", "")
        else:
            decision = check_permission(principal, action)
        results.append(decision)
    return results


__all__ = ["DEFAULT_ACTIONS", "PermissionDecision", "allow", "batch_check_permissions"]
