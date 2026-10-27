"""Risk and usage analytics for Phase 4a.

Aggregates risk trends from Phase 2 audit events and Phase 3 CI/platform
usage data. Provides usage popularity and stale-asset detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RiskTrend:
    """Risk trend summary over a time window."""

    period: str = ""
    total_findings: int = 0
    high_severity: int = 0
    medium_severity: int = 0
    low_severity: int = 0
    trend_direction: str = "stable"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period, "total_findings": self.total_findings,
            "high_severity": self.high_severity, "medium_severity": self.medium_severity,
            "low_severity": self.low_severity, "trend_direction": self.trend_direction,
            "metadata": self.metadata,
        }


@dataclass
class UsageStats:
    """Usage statistics for an asset or group of assets."""

    asset_id: str = ""
    download_count: int = 0
    resolve_count: int = 0
    last_used_at: str = ""
    popularity_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id, "download_count": self.download_count,
            "resolve_count": self.resolve_count, "last_used_at": self.last_used_at,
            "popularity_score": self.popularity_score, "metadata": self.metadata,
        }


class AnalyticsEngine:
    """In-memory analytics engine for risk trends and usage statistics.

    Consumes Phase 2 audit events and Phase 3 platform usage events
    stored in the catalog repository or audit log.
    """

    def __init__(self):
        self._scan_events: list[dict] = []
        self._usage_events: list[dict] = []

    def record_scan(self, asset_id: str, severity: str, finding_type: str = "", timestamp: str = "") -> None:
        self._scan_events.append({"asset_id": asset_id, "severity": severity, "type": finding_type, "ts": timestamp})

    def record_usage(self, asset_id: str, action: str = "download", timestamp: str = "", **meta) -> None:
        self._usage_events.append({"asset_id": asset_id, "action": action, "ts": timestamp, "meta": meta})

    def get_risk_trends(self, *, period: str = "30d") -> RiskTrend:
        high = sum(1 for e in self._scan_events if e["severity"] == "high")
        medium = sum(1 for e in self._scan_events if e["severity"] == "medium")
        low = sum(1 for e in self._scan_events if e["severity"] == "low")
        total = high + medium + low
        return RiskTrend(period=period, total_findings=total, high_severity=high, medium_severity=medium, low_severity=low,
                         trend_direction="increasing" if total > 0 else "stable")

    def get_usage_popularity(self, asset_id: str = "") -> list[UsageStats]:
        counts: dict[str, dict] = {}
        for e in self._usage_events:
            aid = e["asset_id"]
            if asset_id and aid != asset_id: continue
            if aid not in counts:
                counts[aid] = {"download_count": 0, "resolve_count": 0}
            if e["action"] == "download": counts[aid]["download_count"] += 1
            elif e["action"] in ("resolve", "deploy"): counts[aid]["resolve_count"] += 1
        stats = []
        for aid, c in counts.items():
            score = c["download_count"] * 2 + c["resolve_count"] * 3
            stats.append(UsageStats(asset_id=aid, download_count=c["download_count"], resolve_count=c["resolve_count"], popularity_score=score))
        stats.sort(key=lambda s: s.popularity_score, reverse=True)
        return stats

    def get_stale_assets(self, threshold_days: int = 90) -> list[str]:
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=threshold_days)).isoformat()
        used = {e["asset_id"] for e in self._usage_events if e["ts"] >= cutoff}
        all_ids = {e["asset_id"] for e in self._usage_events}
        return sorted(all_ids - used)


__all__ = ["AnalyticsEngine", "RiskTrend", "UsageStats"]
