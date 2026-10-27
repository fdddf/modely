"""Asset analysis implementation."""

from __future__ import annotations

import json
import re
from typing import Optional, List

from ..cataloging.cards import get_card
from ..application.file_queries import classify_file, filter_files, format_file_size, list_repo_files, summarize_files
from ..application.repo_queries import get_repo_info, resolve_repo_ref
from ..application.download_profiles import resolve_download_profile
from ..types import AssetAnalysis, FileInfo

_WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt", ".pth", ".ckpt", ".onnx", ".h5", ".msgpack")
_DATASET_SUFFIXES = (".parquet", ".jsonl", ".csv", ".tsv", ".arrow", ".zip", ".tar", ".tar.gz")
_METADATA_SUFFIXES = (".json", ".yaml", ".yml", ".txt", ".md")
_FORMAT_SUFFIXES = _WEIGHT_SUFFIXES + _DATASET_SUFFIXES + _METADATA_SUFFIXES
_QUANTIZATION_RE = re.compile(r"(?:^|[-_.])(q\d(?:_[a-z0-9]+)*|f16|bf16|fp16|fp32|int8)(?:[-_.]|$)", re.IGNORECASE)


def analyze_resource(
    resource: str,
    *,
    revision: Optional[str] = None,
    token: Optional[str] = None,
    endpoint: Optional[str] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    profile: Optional[str] = None,
    top_files: int = 5,
    deep: bool = False,
    source: str = "auto",
    repo_type: str = "auto",
    get_repo_info_func=None,
    list_repo_files_func=None,
    get_card_func=None,
) -> AssetAnalysis:
    """Analyze metadata, files, card presence, and weight formats for a resource."""
    warnings = []
    if get_repo_info_func is None:
        get_repo_info_func = get_repo_info
    if list_repo_files_func is None:
        list_repo_files_func = list_repo_files
    if get_card_func is None:
        get_card_func = get_card
    include, exclude = resolve_download_profile(profile, include, exclude)
    ref = resolve_repo_ref(resource, revision=revision, token=token, endpoint=endpoint, source=source, repo_type=repo_type) if "://" not in str(resource) else resource
    info = get_repo_info_func(ref, revision=revision, token=token, endpoint=endpoint)
    files = list_repo_files_func(ref, revision=revision, token=token, endpoint=endpoint)
    selected = filter_files(files, include, exclude)
    summary = summarize_files(files, include, exclude)
    largest_files = sorted(selected, key=lambda f: f.size or 0, reverse=True)[:top_files]
    categories = {classify_file(f.path) for f in selected}
    weight_formats = _weight_formats(selected)
    card = get_card_func(ref, revision=revision, token=token, endpoint=endpoint)
    has_config = "config" in categories
    has_tokenizer = "tokenizer" in categories
    has_card = bool(card.text) or "card" in categories
    if not files:
        warnings.append("No files listed")
    if not has_config:
        warnings.append("No config file detected")
    if not has_tokenizer:
        warnings.append("No tokenizer file detected")
    if not has_card:
        warnings.append("No model/dataset card detected")
    warnings.extend(card.warnings)
    metadata = {"profile": profile, "include": include, "exclude": exclude}
    if deep:
        metadata["deep"] = deep_file_analysis(
            selected,
            license_name=info.license,
            has_config=has_config,
            has_tokenizer=has_tokenizer,
            has_card=has_card,
            top_files=top_files,
        )
    return AssetAnalysis(
        info=info,
        summary=summary,
        files=selected,
        largest_files=largest_files,
        weight_formats=weight_formats,
        has_config=has_config,
        has_tokenizer=has_tokenizer,
        has_card=has_card,
        card=card,
        warnings=list(dict.fromkeys(warnings)),
        metadata=metadata,
    )


def deep_file_analysis(
    files: List[FileInfo],
    *,
    license_name: Optional[str] = None,
    has_config: bool = False,
    has_tokenizer: bool = False,
    has_card: bool = False,
    top_files: int = 5,
) -> dict:
    """Return metadata-only deep analysis derived from file names and sizes."""
    formats = {}
    weight_bytes = 0
    dataset_bytes = 0
    quantization = {}
    weight_files = []
    for f in files:
        fmt = _file_format(f.path)
        if fmt:
            bucket = formats.setdefault(fmt, {"count": 0, "bytes": 0})
            bucket["count"] += 1
            bucket["bytes"] += f.size or 0
        if _is_weight_file(f.path):
            weight_bytes += f.size or 0
            weight_files.append(f)
            hint = _quantization_hint(f.path)
            if hint:
                quantization[hint] = quantization.get(hint, 0) + 1
        if _is_dataset_file(f.path):
            dataset_bytes += f.size or 0

    largest_weight_files = [
        {"path": f.path, "size": f.size, "format": _file_format(f.path)}
        for f in sorted(weight_files, key=lambda item: item.size or 0, reverse=True)[:top_files]
    ]
    flags = {
        "has_safetensors": "safetensors" in formats,
        "has_gguf": "gguf" in formats,
        "has_onnx": "onnx" in formats,
        "has_parquet": "parquet" in formats,
        "has_jsonl": "jsonl" in formats,
    }
    risk_flags = _risk_flags(
        license_name=license_name,
        has_config=has_config,
        has_tokenizer=has_tokenizer,
        has_card=has_card,
        weight_bytes=weight_bytes,
    )
    return {
        "formats": formats,
        "weight_bytes": weight_bytes,
        "dataset_bytes": dataset_bytes,
        "largest_weight_files": largest_weight_files,
        "quantization": dict(sorted(quantization.items())),
        **flags,
        "recommended_profiles": _recommended_profiles(weight_bytes, dataset_bytes, flags),
        "risk_flags": risk_flags,
    }


def print_asset_analysis(analysis: AssetAnalysis, *, as_json: bool = False) -> None:
    """Print an asset analysis."""
    if as_json:
        print(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
        return
    info = analysis.info
    print(f"Source:        {info.source}")
    print(f"Repo type:     {info.repo_type}")
    print(f"Repo ID:       {info.repo_id}")
    if info.url:
        print(f"URL:           {info.url}")
    if info.license:
        print(f"License:       {info.license}")
    if info.tags:
        print(f"Tags:          {', '.join(info.tags[:20])}")
    print(f"Files:         {analysis.summary.selected_files}/{analysis.summary.total_files}")
    print(f"Size:          {format_file_size(analysis.summary.selected_size)} / {format_file_size(analysis.summary.total_size)}")
    print(f"Has config:    {analysis.has_config}")
    print(f"Has tokenizer: {analysis.has_tokenizer}")
    print(f"Has card:      {analysis.has_card}")
    if analysis.summary.categories:
        print("Categories:")
        for name in sorted(analysis.summary.categories):
            print(f"  - {name}: {analysis.summary.categories[name]} ({format_file_size(analysis.summary.category_sizes.get(name, 0))})")
    if analysis.weight_formats:
        print("Weight formats:")
        for name, count in sorted(analysis.weight_formats.items()):
            print(f"  - {name}: {count}")
    deep = analysis.metadata.get("deep") if analysis.metadata else None
    if deep:
        print("Deep analysis:")
        print(f"  Weight bytes:  {format_file_size(deep.get('weight_bytes', 0))}")
        print(f"  Dataset bytes: {format_file_size(deep.get('dataset_bytes', 0))}")
        if deep.get("quantization"):
            print(f"  Quantization:  {', '.join(f'{k}:{v}' for k, v in deep['quantization'].items())}")
        if deep.get("recommended_profiles"):
            print(f"  Profiles:      {', '.join(deep['recommended_profiles'])}")
        if deep.get("risk_flags"):
            print(f"  Risk flags:    {', '.join(deep['risk_flags'])}")
    if analysis.largest_files:
        print("Largest files:")
        for f in analysis.largest_files:
            print(f"  - {f.path} ({format_file_size(f.size)})")
    if analysis.warnings:
        print("Warnings:")
        for warning in analysis.warnings:
            print(f"  - {warning}")


def _weight_formats(files: List[FileInfo]) -> dict:
    formats = {}
    for f in files:
        fmt = _file_format(f.path)
        if fmt and _is_weight_file(f.path):
            formats[fmt] = formats.get(fmt, 0) + 1
    return formats


def _file_format(path: str) -> Optional[str]:
    lower = path.lower()
    for suffix in sorted(_FORMAT_SUFFIXES, key=len, reverse=True):
        if lower.endswith(suffix):
            return suffix.lstrip(".").replace(".", "-")
    return None


def _is_weight_file(path: str) -> bool:
    return path.lower().endswith(_WEIGHT_SUFFIXES)


def _is_dataset_file(path: str) -> bool:
    return path.lower().endswith(_DATASET_SUFFIXES)


def _quantization_hint(path: str) -> Optional[str]:
    match = _QUANTIZATION_RE.search(path.rsplit("/", 1)[-1])
    return match.group(1).lower() if match else None


def _risk_flags(*, license_name, has_config, has_tokenizer, has_card, weight_bytes) -> list[str]:
    flags = []
    if not license_name:
        flags.append("missing-license")
    if not has_card:
        flags.append("missing-card")
    if not has_config:
        flags.append("missing-config")
    if not has_tokenizer:
        flags.append("missing-tokenizer")
    if weight_bytes >= 10_000_000_000:
        flags.append("large-weights")
    return flags


def _recommended_profiles(weight_bytes: int, dataset_bytes: int, flags: dict) -> list[str]:
    profiles = ["minimal"]
    if weight_bytes:
        profiles.append("no-weights")
    if flags.get("has_safetensors") or flags.get("has_gguf") or flags.get("has_onnx"):
        profiles.append("inference")
    if dataset_bytes and not weight_bytes:
        profiles.append("full")
    return list(dict.fromkeys(profiles))


__all__ = [name for name in globals() if not name.startswith("_")]
