"""Repository query application services."""

from __future__ import annotations

import json
from typing import Optional

from ..auth import get_token
from ..backend_registry import select_backend
from ..types import RepoInfo, RepoRef
from ..uri import parse_modely_uri, repo_type_candidates, normalize_source


def get_repo_info(ref_or_uri, *, revision: Optional[str] = None, token: Optional[str] = None,
                  endpoint: Optional[str] = None, source: str = "auto", repo_type: str = "auto") -> RepoInfo:
    """Return best-effort repository metadata for any supported source."""
    ref = _resolve_ref(ref_or_uri, source=source, repo_type=repo_type)
    if revision:
        ref.revision = revision
    token = get_token(ref.source, token)
    candidates = _candidate_refs(ref, explicit=(isinstance(ref_or_uri, RepoRef) or "://" in str(ref_or_uri)), repo_type=repo_type)
    errors = []
    for candidate in candidates:
        if revision:
            candidate.revision = revision
        try:
            return _repo_info_for_ref(candidate, token=token, endpoint=endpoint)
        except Exception as exc:
            errors.append(f"{candidate.source}:{candidate.repo_type}: {exc}")
            if len(candidates) == 1:
                raise
    raise Exception(
        "Could not resolve repository info. Tried "
        + ", ".join(f"{c.source}:{c.repo_type}" for c in candidates)
        + ". Use an explicit URI such as hf://datasets/<repo> or pass --repo-type. "
        + "; ".join(errors)
    )


def resolve_repo_ref(ref_or_uri, *, revision: Optional[str] = None, token: Optional[str] = None,
                     endpoint: Optional[str] = None, source: str = "auto", repo_type: str = "auto", get_repo_info_func=None) -> RepoRef:
    """Resolve a resource to a concrete repository reference using metadata probes."""
    if get_repo_info_func is None:
        get_repo_info_func = get_repo_info
    info = get_repo_info_func(ref_or_uri, revision=revision, token=token, endpoint=endpoint, source=source, repo_type=repo_type)
    return RepoRef(info.source, info.repo_type, info.repo_id, revision or info.revision)


def _resolve_ref(ref_or_uri, *, source: str = "auto", repo_type: str = "auto") -> RepoRef:
    if isinstance(ref_or_uri, RepoRef):
        return ref_or_uri
    if "://" in str(ref_or_uri):
        return parse_modely_uri(ref_or_uri)
    src = "hf" if source == "auto" else normalize_source(source)
    return parse_modely_uri(ref_or_uri, source=src, repo_type=repo_type)


def _candidate_refs(ref: RepoRef, *, explicit: bool, repo_type: str) -> list[RepoRef]:
    if explicit or repo_type != "auto":
        return [ref]
    return [RepoRef(ref.source, candidate_type, ref.repo_id, ref.revision, ref.path) for candidate_type in repo_type_candidates("auto", ref.source)]


def _repo_info_for_ref(ref: RepoRef, *, token=None, endpoint=None) -> RepoInfo:
    backend_plugin = select_backend(ref.source, "info")
    return backend_plugin.info(ref, token=token, endpoint=endpoint)


def print_repo_info(info: RepoInfo, *, as_json: bool = False) -> None:
    """Print repository info as table-ish output or JSON."""
    if as_json:
        print(json.dumps(info.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Source:        {info.source}")
    print(f"Repo type:     {info.repo_type}")
    print(f"Repo ID:       {info.repo_id}")
    if info.revision:
        print(f"Revision:      {info.revision}")
    if info.url:
        print(f"URL:           {info.url}")
    if info.author:
        print(f"Author:        {info.author}")
    if info.description:
        print(f"Description:   {info.description}")
    if info.license:
        print(f"License:       {info.license}")
    print(f"Downloads:     {info.downloads}")
    print(f"Likes/Stars:   {info.likes}")
    if info.forks:
        print(f"Forks:         {info.forks}")
    if info.last_modified:
        print(f"Last modified: {info.last_modified}")
    if info.created_at:
        print(f"Created at:    {info.created_at}")
    if info.tags:
        print(f"Tags:          {', '.join(info.tags[:20])}")


__all__ = ["get_repo_info", "resolve_repo_ref", "print_repo_info"]
