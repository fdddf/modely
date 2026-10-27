"""Download application services."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..auth import get_token
from ..backend_registry import select_backend
from ..common import cache as modely_cache
from .download_profiles import resolve_download_profile
from .file_queries import filter_files, list_repo_files
from ..syncing.reliability import checksum_status, diagnose_download_error, normalize_download_options, retry_call
from ..types import RepoRef
from ..uri import concrete_repo_type, format_modely_uri, normalize_repo_type, normalize_source, parse_modely_uri


def _default_prefer(repo_type: str) -> str:
    """Return the default source order for a repo type."""
    return "ms,hf,kaggle,github" if repo_type == "dataset" else "ms,hf,github"


def download_resource(
    resource: str,
    *,
    source: str = "auto",
    repo_type: str = "model",
    revision: Optional[str] = None,
    file: Optional[str] = None,
    cache_dir: Optional[str] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    prefer: str = "ms,hf,github",
    fallback: bool = False,
    force_download: bool = False,
    backend: str = "auto",
    with_lfs: bool = False,
    profile: Optional[str] = None,
    endpoint: Optional[str] = None,
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
    checksum: bool = False,
    resume: bool = True,
    cache_module=modely_cache,
    list_repo_files_func=None,
):
    """Download a resource by URI, explicit source, or auto/fallback source order."""
    include, exclude = resolve_download_profile(profile, include, exclude)
    options = normalize_download_options(
        retries=retries,
        timeout=timeout,
        checksum=checksum,
        resume=resume,
        max_workers=max_workers,
    )
    cache_dir = cache_module.get_cache_dir(cache_dir)

    if "://" in resource:
        ref = parse_modely_uri(resource)
        if revision:
            ref.revision = revision
        if file:
            ref.path = file
        if not fallback:
            return _download_ref(ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                                 include=include, exclude=exclude, force_download=force_download,
                                 backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                                 options=options, list_repo_files_func=list_repo_files_func)
        if prefer == "default":
            prefer = _default_prefer(ref.repo_type)
        errors = []
        for candidate in _fallback_refs_for_uri(ref, prefer):
            try:
                return _download_ref(candidate, cache_dir=cache_dir, local_dir=local_dir, token=token,
                                     include=include, exclude=exclude, force_download=force_download,
                                     backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                                     options=options, list_repo_files_func=list_repo_files_func)
            except Exception as exc:
                errors.append(diagnose_download_error(candidate.source, exc))
        raise Exception("All sources failed: " + "; ".join(errors))

    if source != "auto":
        ref = RepoRef(normalize_source(source), concrete_repo_type(repo_type, source), resource, revision, file)
        return _download_ref(ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                             include=include, exclude=exclude, force_download=force_download,
                             backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                             options=options, list_repo_files_func=list_repo_files_func)

    if prefer == "default":
        prefer = _default_prefer(concrete_repo_type(repo_type, "hf"))

    if source == "auto" and prefer == "fastest":
        from .sources import rank_sources
        ranked = [r.source for r in rank_sources(resource, candidates=["hf", "hf-mirror", "ms", "github", "kaggle"], timeout=options.timeout or 5) if r.ok]
        seen = set()
        prefer = ",".join(s for s in ranked if not (s in seen or seen.add(s))) or _default_prefer(repo_type)

    errors = []
    for src in [s.strip() for s in prefer.split(",") if s.strip()]:
        try:
            ref = RepoRef(normalize_source(src), concrete_repo_type(repo_type, src), resource, revision, file)
            return _download_ref(ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                                 include=include, exclude=exclude, force_download=force_download,
                                 backend=backend, with_lfs=with_lfs, endpoint=endpoint,
                                 options=options, list_repo_files_func=list_repo_files_func)
        except Exception as exc:
            errors.append(diagnose_download_error(src, exc))
            if not fallback:
                raise
    raise Exception("All sources failed: " + "; ".join(errors))


def _download_ref(ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, include=None, exclude=None,
                  force_download=False, backend="auto", with_lfs=False, endpoint=None,
                  options=None, list_repo_files_func=None):
    options = options or normalize_download_options()
    token = get_token(ref.source, token)
    operation = "single_file" if ref.path else "snapshot"
    backend_plugin = select_backend(ref.source, operation, backend=backend)
    result = retry_call(
        lambda: backend_plugin.download(
            ref,
            cache_dir=cache_dir,
            local_dir=local_dir,
            token=token,
            include=include,
            exclude=exclude,
            force_download=force_download,
            with_lfs=with_lfs,
            endpoint=endpoint,
            options=options,
        ),
        retries=options.retries,
        label=f"{ref.source}:{ref.repo_id}" + (f"/{ref.path}" if ref.path else ""),
    )
    return _finalize_download(result, ref, include=include, exclude=exclude, token=token, endpoint=endpoint, options=options, list_repo_files_func=list_repo_files_func)


def _finalize_download(result, ref: RepoRef, *, include=None, exclude=None, token=None, endpoint=None, options=None, list_repo_files_func=None):
    """Run post-download checks and persist repo metadata."""
    _verify_download_checksums(result, ref, include=include, exclude=exclude, token=token, endpoint=endpoint, options=options, list_repo_files_func=list_repo_files_func)
    _persist_repo_info(result, ref, token=token, endpoint=endpoint)
    return result


def _persist_repo_info(download_path, ref: RepoRef, *, token=None, endpoint=None) -> None:
    """Write ``modely-info.json`` sidecar to the downloaded revision directory.

    Fetches repo metadata from the appropriate source plugin and writes it
    alongside the cached files so the catalog and web UI can surface
    license, tags, and other metadata without re-fetching.
    """
    if not download_path:
        return
    try:
        from ..common.cache import write_repo_info
        from .repo_queries import _repo_info_for_ref

        info = _repo_info_for_ref(ref, token=token, endpoint=endpoint)
        if info:
            write_repo_info(str(download_path), info.to_dict())
    except Exception:
        pass  # best-effort; never fail a download because of metadata


def _verify_download_checksums(result, ref: RepoRef, *, include=None, exclude=None, token=None, endpoint=None, options=None, list_repo_files_func=None) -> list[dict]:
    """Verify downloaded files when checksum mode is enabled."""
    if not options or not options.checksum:
        return []

    if list_repo_files_func is None:
        list_repo_files_func = list_repo_files

    remote_files = list_repo_files_func(ref, token=token, endpoint=endpoint)
    if ref.path:
        remote_files = [f for f in remote_files if f.path == ref.path]
    else:
        remote_files = filter_files(remote_files, include, exclude)

    statuses = []
    mismatches = []
    missing_files = []
    for remote in remote_files:
        local_path = _local_download_path(result, remote.path, single_file=bool(ref.path))
        if not local_path or not local_path.exists():
            missing_files.append(remote.path)
            continue
        status = checksum_status(str(local_path), remote.sha256)
        statuses.append(status.to_dict())
        if not status.ok:
            mismatches.append(status)

    if missing_files:
        raise Exception(f"Checksum verification failed; missing downloaded file(s): {', '.join(missing_files[:10])}")
    if mismatches:
        details = ", ".join(f"{s.path}: expected {s.expected}, got {s.actual}" for s in mismatches[:10])
        raise Exception(f"Checksum verification failed: {details}")
    return statuses


def _local_download_path(result, remote_path: str, *, single_file: bool) -> Optional[Path]:
    """Map a backend download result and remote path to a local path."""
    if not result:
        return None
    root = Path(result)
    if single_file:
        return root
    return root / remote_path


def _fallback_refs_for_uri(ref: RepoRef, prefer: str) -> list[RepoRef]:
    refs = [ref]
    for item in [s.strip() for s in prefer.split(",") if s.strip()]:
        if "://" in item:
            candidate = parse_modely_uri(item)
            refs.append(candidate)
            continue
        source = normalize_source(item)
        if source == ref.source:
            continue
        resolved = _resolve_equivalent_ref(ref, source)
        refs.append(resolved or RepoRef(source, normalize_repo_type(ref.repo_type, source), ref.repo_id, ref.revision, ref.path))
    seen = set()
    unique = []
    for item in refs:
        key = (item.source, item.repo_type, item.repo_id, item.revision, item.path)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _resolve_equivalent_ref(ref: RepoRef, source: str) -> Optional[RepoRef]:
    try:
        from .resolve import resolve_resource
        result = resolve_resource(format_modely_uri(ref), source=source, repo_type=normalize_repo_type(ref.repo_type, source), limit=5)
        for candidate in result.candidates:
            if candidate.source == source:
                return RepoRef(candidate.source, candidate.repo_type, candidate.repo_id, ref.revision, ref.path)
    except Exception:
        return None
    return None


__all__ = ["download_resource", "_verify_download_checksums"]
