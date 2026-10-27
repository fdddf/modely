"""Source adapter orchestration for sync jobs."""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from ..storage.checksums import sha256_file
from ..types import FileInfo, RepoRef


@dataclass
class SourceAdapterCapabilities:
    """Capability flags for a source adapter used by sync jobs."""

    list_files: bool = False
    download_file: bool = False
    resolve_revision: bool = False
    checksum: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceCredentialRef:
    """Redacted source credential reference for no-secret adapter configuration."""

    ref: str | None = None
    provider: str | None = None
    scope: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["redacted"] = True
        return payload


class SourceAdapter(Protocol):
    """Minimal protocol for future source adapters."""

    name: str
    capabilities: SourceAdapterCapabilities

    def resolve_revision(self, ref: RepoRef) -> str | None: ...
    def list_files(self, ref: RepoRef) -> list[FileInfo]: ...
    def download_file(self, ref: RepoRef, file: FileInfo | str, destination: str | Path, *, overwrite: bool = False) -> Path: ...


class FixtureSourceAdapter:
    """No-network source adapter backed by a local fixture directory."""

    def __init__(
        self,
        root: str | Path,
        *,
        name: str = "fixture",
        credential: SourceCredentialRef | None = None,
    ):
        self.root = Path(root).expanduser().resolve()
        self.name = name
        self.credential = credential
        metadata: dict[str, Any] = {"network": False, "fixture_root": str(self.root)}
        if credential is not None:
            metadata["credential"] = credential.to_dict()
        self.capabilities = SourceAdapterCapabilities(
            list_files=True,
            download_file=True,
            resolve_revision=True,
            checksum=True,
            metadata=metadata,
        )

    def resolve_revision(self, ref: RepoRef) -> str | None:
        return ref.revision or "fixture"

    def list_files(self, ref: RepoRef) -> list[FileInfo]:
        if not self.root.exists():
            raise FileNotFoundError(f"Fixture root does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Fixture root must be a directory: {self.root}")
        files: list[FileInfo] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            rel = self._relative_fixture_path(path)
            files.append(
                FileInfo(
                    path=rel,
                    size=path.stat().st_size,
                    sha256=sha256_file(str(path)),
                    metadata={
                        "source": ref.source,
                        "repo_type": ref.repo_type,
                        "repo_id": ref.repo_id,
                        "revision": self.resolve_revision(ref),
                        "fixture_root": str(self.root),
                    },
                )
            )
        return sorted(files, key=lambda item: item.path)

    def download_file(self, ref: RepoRef, file: FileInfo | str, destination: str | Path, *, overwrite: bool = False) -> Path:
        file_path = file.path if isinstance(file, FileInfo) else str(file)
        rel = self._safe_relative_path(file_path)
        source = (self.root / rel).resolve()
        self._ensure_inside_root(source)
        if not source.is_file():
            raise FileNotFoundError(f"Fixture file does not exist: {file_path}")
        destination_path = Path(destination).expanduser()
        if destination_path.is_dir() or (not destination_path.exists() and destination_path.suffix == ""):
            target = destination_path / rel
        else:
            target = destination_path
        if target.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target

    def _relative_fixture_path(self, path: Path) -> str:
        try:
            rel = path.resolve().relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Fixture path escapes root: {path}") from exc
        return self._safe_relative_path(rel.as_posix())

    def _safe_relative_path(self, path: str) -> str:
        raw = str(path).replace("\\", "/")
        if raw.startswith("/"):
            raise ValueError(f"Unsafe fixture path: {path}")
        normalized = PurePosixPath(raw)
        if normalized.is_absolute() or any(part == ".." for part in normalized.parts):
            raise ValueError(f"Unsafe fixture path: {path}")
        value = normalized.as_posix()
        if value in {"", "."}:
            raise ValueError("Fixture path must not be empty")
        return value

    def _ensure_inside_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Fixture path escapes root: {path}") from exc


__all__ = [
    "FixtureSourceAdapter",
    "GitHubSourceAdapter",
    "HfSourceAdapter",
    "ModelScopeSourceAdapter",
    "SourceAdapter",
    "SourceAdapterCapabilities",
    "SourceCredentialRef",
]


# ---------------------------------------------------------------------------
# Real source adapters
# ---------------------------------------------------------------------------


class HfSourceAdapter:
    """Hugging Face Hub source adapter implementing the SourceAdapter protocol.

    Wraps ``modely.hf`` download functions with the unified adapter interface.
    """

    def __init__(self, *, token: str | None = None, endpoint: str | None = None):
        self.name = "huggingface"
        self.token = token
        self.endpoint = endpoint
        self.capabilities = SourceAdapterCapabilities(
            list_files=True,
            download_file=True,
            resolve_revision=True,
            checksum=True,
            metadata={"network": True, "source": "hf"},
        )

    def resolve_revision(self, ref: RepoRef) -> str | None:
        return ref.revision or "main"

    def list_files(self, ref: RepoRef) -> list[FileInfo]:
        """List files via the Hugging Face Hub API."""
        from ..hf import list_files as hf_list_files

        return hf_list_files(
            ref.repo_id,
            repo_type=ref.repo_type or "model",
            revision=ref.revision or "main",
            token=self.token,
            endpoint=self.endpoint,
        )

    def download_file(self, ref: RepoRef, file: FileInfo | str, destination: str | Path, *, overwrite: bool = False) -> Path:
        """Download a single file via Hugging Face Hub."""
        from ..hf import hf_file_download

        filename = file.path if isinstance(file, FileInfo) else str(file)
        return hf_file_download(
            ref.repo_id,
            filename,
            repo_type=ref.repo_type or "model",
            revision=ref.revision or "main",
            cache_dir=str(destination),
            token=self.token,
            endpoint=self.endpoint,
        )


class ModelScopeSourceAdapter:
    """ModelScope source adapter implementing the SourceAdapter protocol.

    Wraps ``modely.modelscope`` download functions with the unified adapter interface.
    """

    def __init__(self, *, token: str | None = None):
        self.name = "modelscope"
        self.token = token
        self.capabilities = SourceAdapterCapabilities(
            list_files=True,
            download_file=True,
            resolve_revision=True,
            checksum=True,
            metadata={"network": True, "source": "modelscope"},
        )

    def resolve_revision(self, ref: RepoRef) -> str | None:
        return ref.revision or "master"

    def list_files(self, ref: RepoRef) -> list[FileInfo]:
        """List files via the ModelScope API."""
        from ..modelscope import list_files as ms_list_files

        return ms_list_files(
            ref.repo_id,
            repo_type=ref.repo_type or "model",
            revision=ref.revision or "master",
            token=self.token,
        )

    def download_file(self, ref: RepoRef, file: FileInfo | str, destination: str | Path, *, overwrite: bool = False) -> Path:
        """Download a single file via ModelScope."""
        from ..modelscope import model_file_download, dataset_file_download

        filename = file.path if isinstance(file, FileInfo) else str(file)
        repo_type = ref.repo_type or "model"
        download_fn = model_file_download if repo_type == "model" else dataset_file_download
        result = download_fn(
            ref.repo_id,
            filename,
            revision=ref.revision or "master",
            cache_dir=str(destination),
            token=self.token,
        )
        return Path(result) if result else Path(str(destination))


class GitHubSourceAdapter:
    """GitHub source adapter implementing the SourceAdapter protocol.

    Wraps ``modely.github`` functions with the unified adapter interface.
    """

    def __init__(self, *, token: str | None = None):
        self.name = "github"
        self.token = token
        self.capabilities = SourceAdapterCapabilities(
            list_files=True,
            download_file=True,
            resolve_revision=True,
            checksum=True,
            metadata={"network": True, "source": "github"},
        )

    def resolve_revision(self, ref: RepoRef) -> str | None:
        """Resolve revision, falling back to the default branch if possible."""
        if ref.revision:
            return ref.revision
        try:
            from ..github import get_default_branch
            return get_default_branch(ref.repo_id, token=self.token) or "main"
        except Exception:
            return "main"

    def list_files(self, ref: RepoRef) -> list[FileInfo]:
        """List files via the GitHub Git Trees API."""
        from ..github import github_list_files

        return github_list_files(
            ref.repo_id,
            revision=ref.revision or "main",
            token=self.token,
        )

    def download_file(self, ref: RepoRef, file: FileInfo | str, destination: str | Path, *, overwrite: bool = False) -> Path:
        """Download a single file from GitHub."""
        from ..github import github_file_download

        filename = file.path if isinstance(file, FileInfo) else str(file)
        return github_file_download(
            ref.repo_id,
            filename,
            revision=ref.revision or "main",
            cache_dir=str(destination),
            token=self.token,
        )


class CompositeSourceAdapter:
    """Routes to the correct source adapter based on the resource URI source."""

    def __init__(self, *, adapters: dict[str, type]):
        self._adapters: dict[str, Any] = {}
        self._adapter_classes = adapters
        self.capabilities = SourceAdapterCapabilities(
            list_files=True,
            download_file=True,
            resolve_revision=True,
            checksum=True,
            metadata={"network": True, "source": "composite"},
        )

    def _get(self, source: str) -> Any:
        if source not in self._adapters:
            cls = self._adapter_classes.get(source)
            if cls is None:
                raise ValueError(f"No adapter registered for source: {source}")
            self._adapters[source] = cls()
        return self._adapters[source]

    def resolve_revision(self, ref) -> str | None:
        return self._get(ref.source).resolve_revision(ref)

    def list_files(self, ref) -> list:
        return self._get(ref.source).list_files(ref)

    def download_file(self, ref, file, destination, *, overwrite=False):
        return self._get(ref.source).download_file(ref, file, destination, overwrite=overwrite)
