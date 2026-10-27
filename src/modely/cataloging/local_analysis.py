"""Local filesystem analysis helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..analyze import _weight_formats, deep_file_analysis
from ..files import summarize_files
from ..manifest import read_manifest
from ..types import AssetAnalysis, FileInfo, RepoInfo

_MANIFEST_CANDIDATES = ("modely.lock", "modely-manifest.json")


def analyze_local_path(path: str, *, resource: Optional[str] = None, deep: bool = True) -> AssetAnalysis:
    """Analyze a local model/dataset directory without network access."""
    root = Path(path).expanduser().resolve()
    files = _local_files(root)
    manifest = _read_local_manifest(root)
    if manifest:
        info = RepoInfo(
            manifest.source,
            manifest.repo_type,
            manifest.repo_id,
            revision=manifest.revision,
            metadata={"local_path": str(root), "resource": resource or manifest.metadata.get("resource")},
        )
    else:
        info = RepoInfo("local", "model", resource or root.name, metadata={"local_path": str(root)})
    summary = summarize_files(files)
    categories = set(summary.categories)
    has_config = "config" in categories
    has_tokenizer = "tokenizer" in categories
    has_card = "card" in categories
    weight_formats = _weight_formats(files)
    warnings = []
    if not root.exists():
        warnings.append("Local path does not exist")
    if not files:
        warnings.append("No local files found")
    metadata = {"local": True, "path": str(root)}
    if manifest:
        metadata["manifest"] = manifest.to_dict()
    if deep:
        metadata["deep"] = deep_file_analysis(
            files,
            license_name=info.license,
            has_config=has_config,
            has_tokenizer=has_tokenizer,
            has_card=has_card,
        )
    return AssetAnalysis(
        info=info,
        summary=summary,
        files=files,
        largest_files=sorted(files, key=lambda f: f.size or 0, reverse=True)[:5],
        weight_formats=weight_formats,
        has_config=has_config,
        has_tokenizer=has_tokenizer,
        has_card=has_card,
        warnings=warnings,
        metadata=metadata,
    )


def _local_files(root: Path) -> list[FileInfo]:
    if not root.exists():
        return []
    if root.is_file():
        return [FileInfo(root.name, size=root.stat().st_size)]
    output = []
    for item in root.rglob("*"):
        if item.is_file() and ".git" not in item.parts:
            output.append(FileInfo(str(item.relative_to(root)), size=item.stat().st_size))
    return output


def _read_local_manifest(root: Path):
    for name in _MANIFEST_CANDIDATES:
        candidate = root / name
        if candidate.exists() and candidate.is_file():
            try:
                return read_manifest(str(candidate))
            except Exception:
                return None
    for candidate in sorted(list(root.glob("*.lock")) + list(root.glob("*manifest*.json"))):
        if candidate.is_file():
            try:
                return read_manifest(str(candidate))
            except Exception:
                continue
    return None
