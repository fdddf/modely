"""URI parsing helpers for modely-ai resources."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .types import RepoRef


def github_repo_id_from_url(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    repo = "/".join(parts[:2])
    return repo[:-4] if repo.endswith(".git") else repo


def normalize_github_repo_id(repo_id: str) -> str:
    """Normalize owner/repo input or a GitHub URL to owner/repo."""
    repo_id = github_repo_id_from_url(repo_id) or repo_id.strip().removesuffix(".git")
    if "://" in repo_id or repo_id.count("/") != 1:
        raise ValueError("GitHub repository must be in owner/repo format or a https://github.com/owner/repo URL")
    return repo_id

_SUPPORTED_SOURCES = {"hf", "ms", "github", "kaggle"}
_REPO_TYPE_ALIASES = {
    "model": "model",
    "models": "model",
    "dataset": "dataset",
    "datasets": "dataset",
    "space": "space",
    "spaces": "space",
    "tool": "tool",
    "tools": "tool",
    "repo": "tool",
    "repos": "tool",
    "auto": "auto",
    "competition": "competition",
    "competitions": "competition",
}
_AUTO_REPO_TYPE_CANDIDATES = {
    "hf": ["model", "dataset"],
    "ms": ["model", "dataset"],
    "github": ["tool"],
    "kaggle": ["dataset"],
}


def normalize_source(source: str) -> str:
    """Normalize a source name."""
    if source == "modelscope":
        source = "ms"
    if source == "kg":
        source = "kaggle"
    if source not in _SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    return source


def normalize_repo_type(repo_type: str | None, source: str = "hf") -> str:
    """Normalize repo type aliases such as models -> model."""
    if repo_type is None:
        return _AUTO_REPO_TYPE_CANDIDATES[normalize_source(source)][0]
    normalized = _REPO_TYPE_ALIASES.get(repo_type)
    if normalized is None:
        raise ValueError(f"Unsupported repo type: {repo_type}")
    if source == "github" and normalized not in {"tool", "auto"}:
        return "tool"
    return normalized


def concrete_repo_type(repo_type: str | None, source: str = "hf") -> str:
    """Resolve auto/default repo types to a concrete backend repo type."""
    src = normalize_source(source)
    normalized = normalize_repo_type(repo_type, src)
    if normalized == "auto":
        return _AUTO_REPO_TYPE_CANDIDATES[src][0]
    return normalized


def repo_type_candidates(repo_type: str | None, source: str) -> list[str]:
    """Return concrete repo types to try for a source."""
    src = normalize_source(source)
    normalized = normalize_repo_type(repo_type, src)
    if normalized != "auto":
        return [concrete_repo_type(normalized, src)]
    return list(_AUTO_REPO_TYPE_CANDIDATES[src])


def parse_modely_uri(value: str, *, source: str | None = None, repo_type: str | None = None) -> RepoRef:
    """Parse a modely resource URI or a plain repo id into a RepoRef.

    Supported URI forms include::

        hf://models/gpt2
        hf://datasets/google/fleurs?revision=main&file=README.md
        ms://models/owner/name
        github://owner/repo

    Plain repo ids require an explicit source or default to Hugging Face.
    """
    parsed = urlparse(value)

    github_repo_id = github_repo_id_from_url(value)
    if github_repo_id:
        return RepoRef(source="github", repo_type="tool", repo_id=github_repo_id)

    if parsed.scheme:
        src = normalize_source(parsed.scheme)
        parts = [p for p in parsed.path.split("/") if p]
        if src == "github":
            if parsed.netloc:
                repo_id = "/".join([parsed.netloc, *parts[:1]])
                extra = parts[1:]
            else:
                repo_id = "/".join(parts[:2])
                extra = parts[2:]
            rtype = "tool"
        elif src == "kaggle":
            if not parsed.netloc:
                raise ValueError(f"Missing repo type in URI: {value}")
            rtype = normalize_repo_type(parsed.netloc, src)
            repo_id = "/".join(parts[:2]) if rtype == "dataset" else "/".join(parts[:1])
            extra = parts[2:] if rtype == "dataset" else parts[1:]
        else:
            if not parsed.netloc:
                raise ValueError(f"Missing repo type in URI: {value}")
            rtype = normalize_repo_type(parsed.netloc, src)
            repo_id = "/".join(parts)
            extra = []
        query = parse_qs(parsed.query)
        revision = _first(query.get("revision"))
        file_path = _first(query.get("file")) or _first(query.get("path"))
        if extra and not file_path:
            file_path = "/".join(extra)
        if not repo_id or ((src in {"ms", "github"} or (src == "kaggle" and rtype == "dataset")) and "/" not in repo_id):
            raise ValueError(f"Invalid repository id in URI: {value}")
        return RepoRef(source=src, repo_type=rtype, repo_id=repo_id, revision=revision, path=file_path)

    src = normalize_source(source or "hf")
    return RepoRef(
        source=src,
        repo_type=normalize_repo_type(repo_type, src),
        repo_id=value,
    )


def format_modely_uri(ref: RepoRef) -> str:
    """Format a RepoRef as a modely URI."""
    if ref.source == "github":
        uri = f"github://{ref.repo_id}"
    elif ref.source == "kaggle":
        uri = f"kaggle://{ref.repo_type}s/{ref.repo_id}"
    else:
        uri = f"{ref.source}://{ref.repo_type}s/{ref.repo_id}"
    query = []
    if ref.revision:
        query.append(f"revision={ref.revision}")
    if ref.path:
        query.append(f"file={ref.path}")
    return uri + (("?" + "&".join(query)) if query else "")


def _first(values):
    if not values:
        return None
    return values[0]
