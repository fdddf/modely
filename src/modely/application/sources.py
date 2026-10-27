"""Source profiles and lightweight probing."""

from __future__ import annotations

import json
import time
from typing import Iterable, Optional

import requests

from ..types import ProbeResult, SourceProfile

_BUILTINS = [
    SourceProfile("hf", "hf", "https://huggingface.co", "Hugging Face Hub"),
    SourceProfile("hf-mirror", "hf", "https://hf-mirror.com", "Hugging Face mirror endpoint"),
    SourceProfile("ms", "ms", "https://modelscope.cn", "ModelScope"),
    SourceProfile("github", "github", "https://github.com", "GitHub"),
    SourceProfile("kaggle", "kaggle", "https://www.kaggle.com", "Kaggle datasets and competitions"),
]


def list_source_profiles(source: str = "all") -> list[SourceProfile]:
    """Return built-in source profiles."""
    if source == "all":
        return list(_BUILTINS)
    return [p for p in _BUILTINS if p.source == source or p.name == source]


def probe_source(profile: SourceProfile | str, resource: Optional[str] = None, timeout: float = 5) -> ProbeResult:
    """Probe a source endpoint with a lightweight HTTP request."""
    if isinstance(profile, str):
        matches = list_source_profiles(profile)
        if not matches:
            raise ValueError(f"Unknown source profile: {profile}")
        profile = matches[0]
    url = _probe_url(profile, resource)
    start = time.monotonic()
    try:
        response = requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": "modely-ai"})
        latency = int((time.monotonic() - start) * 1000)
        ok = response.status_code < 500
        return ProbeResult(profile.name, profile.source, profile.endpoint, ok, latency, None if ok else f"HTTP {response.status_code}", {"url": url, "status_code": response.status_code})
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        return ProbeResult(profile.name, profile.source, profile.endpoint, False, latency, str(exc), {"url": url})


def rank_sources(resource: Optional[str] = None, candidates: Optional[Iterable[str]] = None, timeout: float = 5) -> list[ProbeResult]:
    """Probe and rank source profiles by success and latency."""
    profiles = []
    if candidates:
        for candidate in candidates:
            profiles.extend(list_source_profiles(candidate))
    else:
        profiles = list_source_profiles("all")
    results = [probe_source(p, resource=resource, timeout=timeout) for p in profiles]
    return sorted(results, key=lambda r: (not r.ok, r.latency_ms or 10**9))


def print_source_profiles(profiles: list[SourceProfile], *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps([p.to_dict() for p in profiles], indent=2, ensure_ascii=False))
        return
    for p in profiles:
        print(f"{p.name:10} {p.source:7} {p.endpoint}  {p.description}")


def print_probe_results(results: list[ProbeResult], *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        return
    for r in results:
        status = "ok" if r.ok else "fail"
        print(f"{r.profile:10} {r.source:7} {status:4} {r.latency_ms:5} ms  {r.endpoint}" + (f"  {r.error}" if r.error else ""))


def _probe_url(profile: SourceProfile, resource: Optional[str]) -> str:
    base = profile.endpoint.rstrip("/")
    if profile.source == "github":
        return "https://api.github.com"
    return base
