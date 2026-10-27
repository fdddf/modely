"""Source endpoint benchmarking helpers."""

from __future__ import annotations

import json
import time
from typing import Iterable, Optional

import requests

from ..sources import list_source_profiles
from ..types import BenchmarkResult, SourceProfile


def benchmark_sources(resource: Optional[str] = None, *, candidates: Optional[Iterable[str]] = None,
                      url: Optional[str] = None, timeout: float = 5, bytes_limit: int = 1024 * 1024) -> list[BenchmarkResult]:
    """Benchmark source endpoint latency and optional capped URL throughput."""
    profiles = []
    if candidates:
        for candidate in candidates:
            profiles.extend(list_source_profiles(candidate))
    else:
        profiles = list_source_profiles("all")
    return sorted([_benchmark_profile(p, url=url, timeout=timeout, bytes_limit=bytes_limit) for p in profiles],
                  key=lambda r: (not r.ok, r.latency_ms or 10**9))


def print_benchmark_results(results: list[BenchmarkResult], *, as_json: bool = False) -> None:
    """Print benchmark results."""
    if as_json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        return
    for r in results:
        status = "ok" if r.ok else "fail"
        throughput = _format_bps(r.throughput_bps) if r.throughput_bps else "-"
        print(f"{r.profile:10} {r.source:7} {status:4} {r.latency_ms:5} ms  {throughput:>10}  {r.endpoint}" + (f"  {r.error}" if r.error else ""))


def _benchmark_profile(profile: SourceProfile, *, url: Optional[str], timeout: float, bytes_limit: int) -> BenchmarkResult:
    target = url or _endpoint_url(profile)
    start = time.monotonic()
    bytes_read = 0
    try:
        response = requests.get(target, timeout=timeout, stream=True, headers={"User-Agent": "modely-ai"})
        latency_ms = int((time.monotonic() - start) * 1000)
        response.raise_for_status()
        throughput = 0
        if url:
            stream_start = time.monotonic()
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                bytes_read += len(chunk)
                if bytes_read >= bytes_limit:
                    bytes_read = bytes_limit
                    break
            elapsed = max(time.monotonic() - stream_start, 0.001)
            throughput = int(bytes_read / elapsed)
        return BenchmarkResult(profile.name, profile.source, profile.endpoint, True, latency_ms, throughput, bytes_read, metadata={"url": target})
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return BenchmarkResult(profile.name, profile.source, profile.endpoint, False, latency_ms, 0, bytes_read, str(exc), {"url": target})


def _endpoint_url(profile: SourceProfile) -> str:
    if profile.source == "github":
        return "https://api.github.com"
    return profile.endpoint.rstrip("/")


def _format_bps(value: int) -> str:
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024:
            return f"{value:.0f} {unit}"
        value /= 1024
    return f"{value:.0f} TB/s"
