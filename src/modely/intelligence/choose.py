"""Cross-source choice helpers."""

from __future__ import annotations

import json
from typing import Optional

from .decision import decide_resource


def choose_resource(
    query: str,
    *,
    source: str = "all",
    repo_type: str = "model",
    strategy: str = "balanced",
    limit: int = 5,
    threshold: float = 0.35,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    policy: Optional[dict] = None,
) -> dict:
    """Choose the best candidate for a query using shared decision evidence."""
    return decide_resource(
        query,
        source=source,
        repo_type=repo_type,
        strategy=strategy,
        limit=limit,
        threshold=threshold,
        token=token,
        endpoint=endpoint,
        policy=policy,
        probe=(strategy == "fastest"),
    )


def print_choice(result: dict, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(f"Query:    {result['query']}")
    print(f"Strategy: {result['strategy']}")
    rec = result.get("recommended")
    if not rec:
        print("No candidate recommended.")
    else:
        print(f"Recommended: {rec['uri']}")
        print(f"Reason:      {', '.join(rec['reasons']) or '-'}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"  - {warning}")
