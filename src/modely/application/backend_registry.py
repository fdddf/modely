"""Runtime backend registry for source operations."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..types import BackendCapability, RepoRef

_FEATURES = [
    "single_file", "snapshot", "resume", "retries", "timeout", "max_workers",
    "range_requests", "checksum", "auth", "mirror", "search", "info", "files",
]


def supports(**kwargs) -> dict[str, bool]:
    """Build a normalized feature support map."""
    return {name: bool(kwargs.get(name, False)) for name in _FEATURES}


class BackendError(Exception):
    """Base class for backend registry errors."""


class BackendUnavailableError(BackendError):
    """Raised when a selected backend is not available."""


class BackendUnsupportedOperationError(BackendError):
    """Raised when a backend does not support an operation."""


class UnknownBackendError(BackendError):
    """Raised when a backend name is unknown."""


class UnknownSourceError(BackendError):
    """Raised when a source has no registered backend."""


@dataclass
class SourceBackend:
    """A registered backend implementation for one modely source."""

    name: str
    source: str
    kind: str
    supports: dict[str, bool]
    available: bool = True
    requires_extra: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    priority: int = 100
    is_available_func: Optional[Callable[[], bool]] = None

    def is_available(self) -> bool:
        if self.is_available_func is not None:
            return bool(self.is_available_func())
        return bool(self.available)

    def capability(self) -> BackendCapability:
        return BackendCapability(
            self.name,
            self.source,
            self.kind,
            available=self.is_available(),
            requires_extra=self.requires_extra,
            supports=dict(self.supports),
            notes=list(self.notes),
        )

    def ensure_available(self) -> None:
        if self.is_available():
            return
        hint = f" Install with modely-ai[{self.requires_extra}]." if self.requires_extra else ""
        raise BackendUnavailableError(f"Backend '{self.name}' is not available.{hint}")

    def ensure_supports(self, operation: str) -> None:
        if not self.supports.get(operation, False):
            raise BackendUnsupportedOperationError(f"Backend '{self.name}' does not support {operation}.")

    def info(self, ref: RepoRef, **kwargs):
        self.ensure_supports("info")
        self.ensure_available()

    def files(self, ref: RepoRef, **kwargs):
        self.ensure_supports("files")
        self.ensure_available()

    def download(self, ref: RepoRef, **kwargs):
        self.ensure_available()
        operation = "single_file" if ref.path else "snapshot"
        self.ensure_supports(operation)


class HuggingFaceSdkBackend(SourceBackend):
    def info(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().info(ref, token=token, endpoint=endpoint, **kwargs)
        from ..hf import get_repo_info
        return get_repo_info(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision or "main", token=token, endpoint=endpoint)

    def files(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().files(ref, token=token, endpoint=endpoint, **kwargs)
        from ..hf import list_files
        return list_files(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision or "main", token=token, endpoint=endpoint)

    def download(self, ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, include=None, exclude=None,
                 force_download=False, options=None, **kwargs):
        super().download(ref, cache_dir=cache_dir, local_dir=local_dir, token=token, include=include, exclude=exclude,
                         force_download=force_download, options=options, **kwargs)
        from ..hf import hf_file_download, snapshot_download
        if ref.path:
            return hf_file_download(ref.repo_id, ref.path, repo_type=ref.repo_type, revision=ref.revision or "main",
                                    cache_dir=cache_dir, local_dir=local_dir, token=token,
                                    force_download=force_download,
                                    resume_download=getattr(options, "resume", True))
        return snapshot_download(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision or "main",
                                 cache_dir=cache_dir, local_dir=local_dir, token=token,
                                 allow_patterns=include, ignore_patterns=exclude,
                                 force_download=force_download, max_workers=getattr(options, "max_workers", None))


class ModelScopeLightweightBackend(SourceBackend):
    def info(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().info(ref, token=token, endpoint=endpoint, **kwargs)
        from ..modelscope import get_repo_info
        return get_repo_info(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, token=token)

    def files(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().files(ref, token=token, endpoint=endpoint, **kwargs)
        from ..modelscope import list_files
        return list_files(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, token=token)

    def download(self, ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, include=None, exclude=None,
                 force_download=False, options=None, **kwargs):
        super().download(ref, cache_dir=cache_dir, local_dir=local_dir, token=token, include=include, exclude=exclude,
                         force_download=force_download, options=options, **kwargs)
        from ..modelscope import dataset_file_download, model_file_download, snapshot_download
        if ref.path and ref.repo_type == "dataset":
            return dataset_file_download(ref.repo_id, ref.path, revision=ref.revision, cache_dir=cache_dir,
                                         local_dir=local_dir, token=token, backend="lightweight")
        if ref.path:
            return model_file_download(ref.repo_id, ref.path, revision=ref.revision, cache_dir=cache_dir,
                                       local_dir=local_dir, token=token, backend="lightweight")
        return snapshot_download(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, cache_dir=cache_dir,
                                 local_dir=local_dir, token=token, force_download=force_download,
                                 allow_patterns=include, ignore_patterns=exclude, backend="lightweight")


class ModelScopeOfficialBackend(SourceBackend):
    def download(self, ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, include=None, exclude=None,
                 force_download=False, options=None, **kwargs):
        super().download(ref, cache_dir=cache_dir, local_dir=local_dir, token=token, include=include, exclude=exclude,
                         force_download=force_download, options=options, **kwargs)
        from ..modelscope import dataset_file_download, model_file_download, snapshot_download
        if ref.path and ref.repo_type == "dataset":
            return dataset_file_download(ref.repo_id, ref.path, revision=ref.revision, cache_dir=cache_dir,
                                         local_dir=local_dir, token=token, backend="official")
        if ref.path:
            return model_file_download(ref.repo_id, ref.path, revision=ref.revision, cache_dir=cache_dir,
                                       local_dir=local_dir, token=token, backend="official")
        return snapshot_download(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, cache_dir=cache_dir,
                                 local_dir=local_dir, token=token, force_download=force_download,
                                 allow_patterns=include, ignore_patterns=exclude, backend="official")


class GitHubHttpBackend(SourceBackend):
    def info(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().info(ref, token=token, endpoint=endpoint, **kwargs)
        from ..github import github_repo_info
        return github_repo_info(ref.repo_id, revision=ref.revision or "main", token=token)

    def files(self, ref: RepoRef, *, token=None, release=None, **kwargs):
        super().files(ref, token=token, release=release, **kwargs)
        from ..github import github_list_files, github_release_assets
        if release:
            return github_release_assets(ref.repo_id, release=release, token=token)
        return github_list_files(ref.repo_id, revision=ref.revision or "main", token=token)

    def download(self, ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, force_download=False, options=None, **kwargs):
        super().download(ref, cache_dir=cache_dir, local_dir=local_dir, token=token, force_download=force_download, options=options, **kwargs)
        from ..github import github_file_download
        return github_file_download(ref.repo_id, ref.path, revision=ref.revision or "main", cache_dir=cache_dir,
                                    local_dir=local_dir, token=token, force_download=force_download,
                                    timeout=getattr(options, "timeout", None))


class GitHubGitBackend(GitHubHttpBackend):
    def download(self, ref: RepoRef, *, cache_dir=None, local_dir=None, token=None, include=None, exclude=None,
                 force_download=False, with_lfs=False, options=None, **kwargs):
        if ref.path:
            return GitHubHttpBackend.download(self, ref, cache_dir=cache_dir, local_dir=local_dir, token=token,
                                             force_download=force_download, options=options, **kwargs)
        SourceBackend.download(self, ref, cache_dir=cache_dir, local_dir=local_dir, token=token, include=include,
                               exclude=exclude, force_download=force_download, options=options, **kwargs)
        from ..github import github_clone
        return github_clone(ref.repo_id, revision=ref.revision or "main", cache_dir=cache_dir, local_dir=local_dir,
                            token=token, with_lfs=with_lfs, force_download=force_download,
                            allow_patterns=include, ignore_patterns=exclude)


class KaggleApiBackend(SourceBackend):
    def info(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().info(ref, token=token, endpoint=endpoint, **kwargs)
        from ..kaggle import kaggle_repo_info
        return kaggle_repo_info(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, token=token)

    def files(self, ref: RepoRef, *, token=None, endpoint=None, **kwargs):
        super().files(ref, token=token, endpoint=endpoint, **kwargs)
        from ..kaggle import kaggle_list_files
        return kaggle_list_files(ref.repo_id, repo_type=ref.repo_type, revision=ref.revision, token=token)

    def download(self, ref: RepoRef, *, cache_dir=None, local_dir=None, force_download=False, options=None, **kwargs):
        super().download(ref, cache_dir=cache_dir, local_dir=local_dir, force_download=force_download, options=options, **kwargs)
        from ..kaggle import kaggle_download
        return kaggle_download(ref.repo_id, repo_type=ref.repo_type, file=ref.path,
                               local_dir=local_dir, cache_dir=cache_dir, force_download=force_download)


_BACKENDS: dict[str, SourceBackend] = {}
_ALIASES = {"hf": "hf-sdk", "ms": "modelscope-lightweight", "modelscope": "modelscope-lightweight", "github": "github-git", "kaggle": "kaggle-api"}


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def register_backend(backend: SourceBackend) -> SourceBackend:
    """Register a backend and return it."""
    if backend.name in _BACKENDS:
        raise UnknownBackendError(f"Backend already registered: {backend.name}")
    _BACKENDS[backend.name] = backend
    return backend


def _register_builtins() -> None:
    if _BACKENDS:
        return
    register_backend(HuggingFaceSdkBackend("hf-sdk", "hf", "official-sdk", supports(single_file=True, snapshot=True, resume=True, retries=True, timeout=True, max_workers=True, checksum=True, auth=True, mirror=True, search=True, info=True, files=True), priority=10))
    register_backend(SourceBackend("hf-xet", "hf", "transport", supports(snapshot=True, resume=True, retries=True, max_workers=True, auth=True, mirror=True), available=_has_module("hf_xet"), requires_extra="hf_xet", notes=["Optional high-performance Hugging Face transport when installed/configured."], priority=50))
    register_backend(ModelScopeOfficialBackend("modelscope-official", "ms", "official-sdk", supports(single_file=True, snapshot=True, resume=True, retries=True, timeout=True, auth=True), available=_has_module("modelscope"), requires_extra="modelscope", priority=10))
    register_backend(ModelScopeLightweightBackend("modelscope-lightweight", "ms", "http", supports(single_file=True, snapshot=True, resume=True, retries=True, timeout=True, range_requests=True, checksum=True, auth=True, mirror=True, info=True, files=True), priority=20))
    register_backend(GitHubGitBackend("github-git", "github", "git", supports(snapshot=True, single_file=True, retries=True, timeout=True, auth=True, files=True, info=True), notes=["Git clone backend; timeout/max-worker controls are limited."], priority=10))
    register_backend(GitHubHttpBackend("github-http", "github", "http", supports(single_file=True, retries=True, timeout=True, auth=True, info=True, files=True), priority=20))
    register_backend(KaggleApiBackend("kaggle-api", "kaggle", "official-api", supports(single_file=True, snapshot=True, retries=True, auth=True, search=True, info=True, files=True), available=_has_module("kaggle"), requires_extra="kaggle", priority=10))
    register_backend(SourceBackend("generic-http", "http", "http", supports(single_file=True, resume=True, retries=True, timeout=True, range_requests=True, checksum=True), available=False, notes=["Declared for future generic URL support; not wired as a first-class source yet."], priority=100))


def list_backend_plugins() -> list[SourceBackend]:
    _register_builtins()
    return list(_BACKENDS.values())


def get_backend_plugin(name: str) -> SourceBackend:
    _register_builtins()
    key = _ALIASES.get(name, name)
    if key not in _BACKENDS:
        raise UnknownBackendError(f"Unknown backend: {name}")
    return _BACKENDS[key]


def list_capabilities() -> list[BackendCapability]:
    return [backend.capability() for backend in list_backend_plugins()]


def get_capability(name: str) -> BackendCapability:
    return get_backend_plugin(name).capability()


def select_backend(source: str, operation: str, backend: str = "auto") -> SourceBackend:
    """Select a backend for a source operation."""
    _register_builtins()
    candidates = [item for item in _BACKENDS.values() if item.source == source and item.supports.get(operation, False)]
    if not candidates:
        raise UnknownSourceError(f"No backend for source '{source}' supports {operation}.")
    if backend not in {None, "auto", "official", "lightweight"}:
        selected = get_backend_plugin(backend)
        if selected.source != source:
            raise UnknownBackendError(f"Backend '{backend}' is for source '{selected.source}', not '{source}'.")
        selected.ensure_supports(operation)
        selected.ensure_available()
        return selected
    if backend == "official":
        candidates = [item for item in candidates if item.kind in {"official-sdk", "official-api"}]
    elif backend == "lightweight":
        candidates = [item for item in candidates if item.kind in {"http", "git"}]
    else:
        candidates = sorted(candidates, key=lambda item: item.priority)
    if not candidates:
        raise BackendUnsupportedOperationError(f"No {backend} backend for source '{source}' supports {operation}.")
    unavailable = []
    for item in sorted(candidates, key=lambda item: item.priority):
        if item.is_available():
            return item
        unavailable.append(item.name)
    raise BackendUnavailableError(f"No available backend for source '{source}' supports {operation}: {', '.join(unavailable)}")
