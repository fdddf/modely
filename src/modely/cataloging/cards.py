"""Catalog card helpers."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import requests

from ..auth import get_token
from ..application.repo_queries import resolve_repo_ref
from ..types import AssetCard, RepoRef
from ..uri import parse_modely_uri

_CARD_NAMES = ("README.md", "README.rst", "README.txt", "readme.md")


def parse_card_text(text: str) -> dict:
    """Parse dependency-free YAML-like frontmatter from card text."""
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}
    current_key = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(stripped[1:].strip().strip('"\''))
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"\'')
        if not key:
            continue
        current_key = key
        if value == "":
            data[key] = []
        elif value.startswith("[") and value.endswith("]"):
            data[key] = [v.strip().strip('"\'') for v in value[1:-1].split(",") if v.strip()]
        elif "," in value:
            data[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            data[key] = value
    return data


def extract_card_metadata(data: dict) -> dict:
    """Extract common normalized model/dataset card fields."""
    aliases = {
        "license": ["license", "licence"],
        "tags": ["tags", "tag"],
        "pipeline_tag": ["pipeline_tag", "task", "task_type"],
        "library_name": ["library_name", "library"],
        "language": ["language", "languages"],
        "datasets": ["datasets", "dataset"],
        "metrics": ["metrics", "metric"],
        "base_model": ["base_model", "base_model_name", "base_models"],
    }
    normalized = {}
    for target, names in aliases.items():
        for name in names:
            if name in data:
                normalized[target] = data[name]
                break
    return normalized


def get_card(resource: str | RepoRef, *, revision: Optional[str] = None, token: Optional[str] = None,
             endpoint: Optional[str] = None, source: str = "auto", repo_type: str = "auto",
             get_hf_card_func=None, get_github_card_func=None, get_ms_card_func=None) -> AssetCard:
    """Fetch a best-effort card/README for a resource."""
    if isinstance(resource, RepoRef):
        ref = resource
    elif "://" in str(resource):
        ref = parse_modely_uri(resource)
    else:
        ref = resolve_repo_ref(resource, revision=revision, token=token, endpoint=endpoint, source=source, repo_type=repo_type)
    if revision:
        ref.revision = revision
    token = get_token(ref.source, token)
    warnings = []
    text = ""
    path = None
    try:
        if ref.source == "hf":
            text, path = (get_hf_card_func or _get_hf_card)(ref, token=token, endpoint=endpoint)
        elif ref.source == "github":
            text, path = (get_github_card_func or _get_github_card)(ref, token=token)
        elif ref.source == "ms":
            text, path = (get_ms_card_func or _get_ms_card)(ref, token=token)
        else:
            warnings.append(f"Unsupported source for card: {ref.source}")
    except Exception as exc:
        warnings.append(str(exc))
    if not text:
        warnings.append("No card/README found")
    data = parse_card_text(text)
    return AssetCard(
        source=ref.source,
        repo_type=ref.repo_type,
        repo_id=ref.repo_id,
        revision=ref.revision,
        path=path,
        text=text,
        data=data,
        warnings=warnings,
        metadata={"normalized": extract_card_metadata(data)},
    )


def print_card(card: AssetCard, *, as_json: bool = False) -> None:
    """Print card content or JSON metadata."""
    if as_json:
        print(json.dumps(card.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Source:    {card.source}")
    print(f"Repo type: {card.repo_type}")
    print(f"Repo ID:   {card.repo_id}")
    if card.path:
        print(f"Path:      {card.path}")
    if card.data:
        print("Frontmatter:")
        for key, value in card.data.items():
            print(f"  {key}: {value}")
    if card.warnings:
        print("Warnings:")
        for warning in card.warnings:
            print(f"  - {warning}")
    if card.text:
        print("\n" + card.text)


def _get_hf_card(ref: RepoRef, *, token=None, endpoint=None):
    from huggingface_hub import hf_hub_download
    with TemporaryDirectory() as tmp:
        path = hf_hub_download(
            repo_id=ref.repo_id,
            filename="README.md",
            repo_type=ref.repo_type,
            revision=ref.revision or "main",
            token=token,
            endpoint=endpoint,
            local_dir=tmp,
        )
        return Path(path).read_text(encoding="utf-8", errors="replace"), "README.md"


def _get_github_card(ref: RepoRef, *, token=None):
    headers = {"User-Agent": "modely-ai"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    revision = ref.revision or "main"
    for name in _CARD_NAMES:
        url = f"https://raw.githubusercontent.com/{ref.repo_id}/{revision}/{name}"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200 and r.text:
            return r.text, name
    return "", None


def _get_ms_card(ref: RepoRef, *, token=None):
    from ..modelscope import dataset_file_download, model_file_download
    with TemporaryDirectory() as tmp:
        for name in _CARD_NAMES:
            try:
                if ref.repo_type == "dataset":
                    path = dataset_file_download(ref.repo_id, name, revision=ref.revision, local_dir=tmp, token=token, backend="lightweight")
                else:
                    path = model_file_download(ref.repo_id, name, revision=ref.revision, local_dir=tmp, token=token, backend="lightweight")
                if path and Path(path).exists():
                    return Path(path).read_text(encoding="utf-8", errors="replace"), name
            except Exception:
                continue
    return "", None


__all__ = [name for name in globals() if not name.startswith("_")]
