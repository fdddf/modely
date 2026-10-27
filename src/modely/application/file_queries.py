"""File query application services."""

from __future__ import annotations

import fnmatch
import json
from typing import Iterable, List

from ..auth import get_token
from ..backend_registry import select_backend
from .repo_queries import resolve_repo_ref
from ..types import FileInfo, FileSummary, RepoRef
from ..uri import parse_modely_uri


def format_file_size(size_bytes):
    """Format bytes into human-readable form."""
    if size_bytes is None or size_bytes == 0:
        return "-"
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes} B"


def list_repo_files(ref_or_uri, *, revision=None, token=None, endpoint=None, release=None, source: str = "auto", repo_type: str = "auto", resolve_repo_ref_func=None) -> List[FileInfo]:
    """List files for any supported source."""
    if isinstance(ref_or_uri, RepoRef):
        ref = ref_or_uri
    elif "://" in str(ref_or_uri):
        ref = parse_modely_uri(ref_or_uri)
    else:
        if resolve_repo_ref_func is None:
            resolve_repo_ref_func = resolve_repo_ref
        ref = resolve_repo_ref_func(ref_or_uri, revision=revision, token=token, endpoint=endpoint, source=source, repo_type=repo_type)
    if revision:
        ref.revision = revision
    token = get_token(ref.source, token)
    backend_plugin = select_backend(ref.source, "files")
    return backend_plugin.files(ref, token=token, endpoint=endpoint, release=release)


def filter_files(files: Iterable[FileInfo], allow_patterns=None, ignore_patterns=None) -> List[FileInfo]:
    """Apply include/exclude glob filters to FileInfo objects."""
    filtered = [f for f in files if getattr(f, "type", "blob") != "tree"]
    if allow_patterns:
        filtered = [f for f in filtered if any(fnmatch.fnmatch(f.path, p) for p in allow_patterns)]
    if ignore_patterns:
        filtered = [f for f in filtered if not any(fnmatch.fnmatch(f.path, p) for p in ignore_patterns)]
    return filtered


def classify_file(path: str) -> str:
    """Classify a repository file into a model asset category."""
    name = path.rsplit("/", 1)[-1].lower()
    if name.startswith("readme") or name.endswith(".md"):
        return "card"
    if name.startswith("config") and name.endswith(".json") or name in {"params.json", "generation_config.json"}:
        return "config"
    if name.startswith("tokenizer") or name in {"vocab.txt", "merges.txt", "special_tokens_map.json", "tokenizer_config.json"} or name.endswith(".model"):
        return "tokenizer"
    if name.endswith(".safetensors"):
        return "safetensors"
    if name.endswith(".gguf"):
        return "gguf"
    if name.endswith((".bin", ".pt", ".pth", ".ckpt", ".h5", ".msgpack", ".onnx")):
        return "weights"
    if name.endswith((".json", ".yaml", ".yml")):
        return "metadata"
    return "other"


def summarize_files(files: Iterable[FileInfo], include=None, exclude=None) -> FileSummary:
    """Summarize total and selected files after include/exclude filtering."""
    normalized = [_normalize_file(f) for f in files]
    blobs = [f for f in normalized if f.type != "tree"]
    selected = filter_files(blobs, include, exclude)
    categories = {}
    category_sizes = {}
    for f in selected:
        category = classify_file(f.path)
        categories[category] = categories.get(category, 0) + 1
        category_sizes[category] = category_sizes.get(category, 0) + (f.size or 0)
    return FileSummary(
        total_files=len(blobs),
        total_size=sum(f.size or 0 for f in blobs),
        selected_files=len(selected),
        selected_size=sum(f.size or 0 for f in selected),
        categories=categories,
        category_sizes=category_sizes,
    )


def print_file_summary(summary: FileSummary) -> None:
    """Print a compact file summary."""
    print("Summary:")
    print(f"  Total files:    {summary.total_files} ({format_file_size(summary.total_size)})")
    print(f"  Selected files: {summary.selected_files} ({format_file_size(summary.selected_size)})")
    if summary.categories:
        print("  Categories:")
        for name in sorted(summary.categories):
            print(f"    - {name}: {summary.categories[name]} ({format_file_size(summary.category_sizes.get(name, 0))})")


def print_file_list(files, source, repo_id, *, as_json=False, summary=False):
    """Print a formatted file list."""
    if as_json:
        payload = [_file_to_dict(f) for f in files]
        if summary:
            payload = {"files": payload, "summary": summarize_files(files).to_dict()}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if not files:
        print(f"No files found in {repo_id}")
        return
    headers = ["Path", "Size", "Type"]
    rows = []
    col_widths = [len(h) for h in headers]
    for d in _file_rows(files):
        row = [d.get("path", "-"), format_file_size(d.get("size", 0)), d.get("type", "blob")]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    print(f"\n[{source.upper()}] {repo_id}\n")
    print("  ".join(h.ljust(w) for h, w in zip(headers, col_widths)))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        path = str(row[0])
        if len(path) > 70:
            path = path[:67] + "..."
        print(f"{path.ljust(col_widths[0])}  {str(row[1]).ljust(col_widths[1])}  {str(row[2]).ljust(col_widths[2])}")
    print(f"\n{len(files)} file(s) shown.\n")
    if summary:
        print_file_summary(summarize_files(files))
        print()


def print_file_tree(files, *, as_json=False):
    """Print files grouped as a lightweight tree with categories."""
    rows = sorted(_file_rows(files), key=lambda item: item["path"])
    if as_json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        print("No files found.")
        return
    for row in rows:
        path = row["path"]
        depth = path.count("/")
        name = path.rsplit("/", 1)[-1]
        prefix = "  " * depth + "- "
        print(f"{prefix}{name} [{row['category']}] {format_file_size(row['size'])}")


def do_dry_run(source, repo_id, repo_type, revision, allow_patterns, ignore_patterns, files):
    """Simulate a download and print a summary."""
    normalized = [_normalize_file(f) for f in files]
    blobs = [f for f in normalized if f.type != "tree"]
    filtered = filter_files(blobs, allow_patterns, ignore_patterns)
    total_size = sum(f.size or 0 for f in filtered)
    print(f"\n[{source.upper()}] {repo_id} (dry-run)")
    print(f"  Repository type: {repo_type}")
    print(f"  Revision:        {revision}")
    print(f"  Total files:     {len(blobs)}")
    if allow_patterns:
        print(f"  Include:         {' '.join(allow_patterns)}")
    if ignore_patterns:
        print(f"  Exclude:         {' '.join(ignore_patterns)}")
    print(f"  Would download:  {len(filtered)} file(s), {format_file_size(total_size)}")
    print()


def _file_rows(files):
    rows = []
    for f in files:
        normalized = _normalize_file(f)
        rows.append({**normalized.to_dict(), "category": classify_file(normalized.path)})
    return rows


def _normalize_file(value):
    if isinstance(value, FileInfo):
        return value
    return FileInfo(
        path=value.get("Path", value.get("path", "")),
        size=value.get("Size", value.get("size", 0)) or 0,
        type=value.get("Type", value.get("type", "blob")),
        sha256=value.get("Sha256", value.get("sha256")),
        download_url=value.get("download_url"),
        metadata=value,
    )


def _file_to_dict(value):
    return _normalize_file(value).to_dict()


__all__ = ["format_file_size", "list_repo_files", "filter_files", "classify_file", "summarize_files", "print_file_summary", "print_file_list", "print_file_tree", "do_dry_run"]
