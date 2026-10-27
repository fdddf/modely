"""Display formatting for modely-ai search results."""

import json
from typing import List

from .types import SearchResult

_MAX_ID_WIDTH = 45
_MAX_URL_WIDTH = 55


def _truncate_url(url: str) -> str:
    """Truncate long URLs for table display."""
    if len(url) > _MAX_URL_WIDTH:
        return url[:_MAX_URL_WIDTH - 3] + "..."
    return url


def _format_count(n: int) -> str:
    """Format large numbers into human-readable form."""
def _format_count(n: int | None) -> str:
    """Format large numbers into human-readable form."""
    if n is None:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _format_date(d: str | None) -> str:
    """Extract YYYY-MM-DD from an ISO 8601 string."""
    if not d:
        return "-"
    return d[:10]


def _truncate_id(repo_id: str) -> str:
    """Truncate long repo IDs for table display."""
    if len(repo_id) > _MAX_ID_WIDTH:
        return repo_id[:_MAX_ID_WIDTH - 3] + "..."
    return repo_id


def format_table(results: List[SearchResult]) -> str:
    """Format search results as a compact terminal table.

    Returns a multi-line string suitable for printing directly.
    """
    if not results:
        return "No results found."

    headers = ["Source", "Type", "ID", "Task", "Downloads", "Likes", "Created", "Last Modified", "URL"]
    rows = []
    col_widths = [len(h) for h in headers]

    for r in results:
        row = [
            r.source.upper(),
            r.repo_type or "-",
            _truncate_id(r.id),
            r.pipeline_tag or "-",
            _format_count(r.downloads),
            _format_count(r.likes),
            _format_date(r.created_at),
            _format_date(r.last_modified),
            _truncate_url(r.url),
        ]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Build table lines
    separator = "  ".join("-" * w for w in col_widths)
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))

    lines = [header_line, separator]
    for row in rows:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, col_widths)))
    lines.append(f"\n{len(results)} result(s) shown.")
    return "\n".join(lines)


def format_json(results: List[SearchResult]) -> str:
    """Format search results as pretty-printed JSON."""

    def _serialize(r: SearchResult) -> dict:
        return r.to_dict()

    return json.dumps([_serialize(r) for r in results], indent=2, ensure_ascii=False)
