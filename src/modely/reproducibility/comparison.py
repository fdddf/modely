"""Cross-resource comparison implementation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import PurePosixPath
from typing import Optional

from ..intelligence.analysis import analyze_resource
from ..application.file_queries import format_file_size
from ..types import ComparisonResult


def compare_resources(
    left: str,
    right: str,
    *,
    revision_left: Optional[str] = None,
    revision_right: Optional[str] = None,
    token: Optional[str] = None,
    include_files: bool = False,
    include_card: bool = False,
    include_formats: bool = False,
    deep: bool = False,
    analyze_resource_func=None,
) -> ComparisonResult:
    """Compare two resources by analyzing both sides."""
    if analyze_resource_func is None:
        analyze_resource_func = analyze_resource
    left_analysis = analyze_resource_func(left, revision=revision_left, token=token, deep=deep)
    right_analysis = analyze_resource_func(right, revision=revision_right, token=token, deep=deep)
    left_tags = set(left_analysis.info.tags or [])
    right_tags = set(right_analysis.info.tags or [])
    size_delta = (left_analysis.summary.selected_size or 0) - (right_analysis.summary.selected_size or 0)
    file_count_delta = (left_analysis.summary.selected_files or 0) - (right_analysis.summary.selected_files or 0)
    warnings = [f"left: {w}" for w in left_analysis.warnings] + [f"right: {w}" for w in right_analysis.warnings]
    summary = {
        "left_id": left_analysis.info.repo_id,
        "right_id": right_analysis.info.repo_id,
        "left_source": left_analysis.info.source,
        "right_source": right_analysis.info.source,
    }
    if include_files:
        summary["files"] = _compare_files(left_analysis.files, right_analysis.files)
    if include_card:
        summary["card"] = _compare_cards(left_analysis, right_analysis)
    if include_formats or deep:
        summary["formats"] = _compare_formats(left_analysis, right_analysis, include_deep=deep)
    return ComparisonResult(
        left=left_analysis,
        right=right_analysis,
        same_license=(left_analysis.info.license or None) == (right_analysis.info.license or None),
        shared_tags=sorted(left_tags & right_tags),
        different_tags={"left_only": sorted(left_tags - right_tags), "right_only": sorted(right_tags - left_tags)},
        size_delta=size_delta,
        file_count_delta=file_count_delta,
        summary=summary,
        warnings=warnings,
    )


def print_comparison(result: ComparisonResult, *, as_json: bool = False) -> None:
    """Print a resource comparison."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    left = result.left
    right = result.right
    rows = [
        ("Source", left.info.source, right.info.source),
        ("Repo ID", left.info.repo_id, right.info.repo_id),
        ("License", left.info.license or "-", right.info.license or "-"),
        ("Downloads", str(left.info.downloads), str(right.info.downloads)),
        ("Likes/Stars", str(left.info.likes), str(right.info.likes)),
        ("Forks", str(left.info.forks), str(right.info.forks)),
        ("Files", str(left.summary.selected_files), str(right.summary.selected_files)),
        ("Size", format_file_size(left.summary.selected_size), format_file_size(right.summary.selected_size)),
        ("Weight formats", ", ".join(sorted(left.weight_formats)) or "-", ", ".join(sorted(right.weight_formats)) or "-"),
        ("Has config", str(left.has_config), str(right.has_config)),
        ("Has tokenizer", str(left.has_tokenizer), str(right.has_tokenizer)),
        ("Has card", str(left.has_card), str(right.has_card)),
    ]
    widths = [max(len(str(r[i])) for r in ([('Field', 'Left', 'Right')] + rows)) for i in range(3)]
    print("  ".join(v.ljust(widths[i]) for i, v in enumerate(("Field", "Left", "Right"))))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
    print(f"\nFile count delta: {result.file_count_delta}")
    print(f"Size delta:       {format_file_size(abs(result.size_delta))} ({'left larger' if result.size_delta > 0 else 'right larger' if result.size_delta < 0 else 'same'})")
    if result.shared_tags:
        print(f"Shared tags:      {', '.join(result.shared_tags[:20])}")
    _print_detail_summary(result.summary)
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")


def _compare_files(left_files, right_files) -> dict:
    left_by_path = {f.path: f for f in left_files}
    right_by_path = {f.path: f for f in right_files}
    left_paths = set(left_by_path)
    right_paths = set(right_by_path)
    changed = []
    for path in sorted(left_paths & right_paths):
        left = left_by_path[path]
        right = right_by_path[path]
        if (left.size or 0) != (right.size or 0) or (left.sha256 and right.sha256 and left.sha256 != right.sha256):
            changed.append({
                "path": path,
                "left_size": left.size,
                "right_size": right.size,
                "left_sha256": left.sha256,
                "right_sha256": right.sha256,
            })
    common = left_paths & right_paths
    union = left_paths | right_paths
    checksum_matches = []
    checksum_mismatches = []
    lfs_matches = []
    lfs_mismatches = []
    for path in sorted(common):
        left = left_by_path[path]
        right = right_by_path[path]
        if left.sha256 and right.sha256:
            target = checksum_matches if left.sha256 == right.sha256 else checksum_mismatches
            target.append(path if target is checksum_matches else {"path": path, "left_sha256": left.sha256, "right_sha256": right.sha256})
        left_oid = (left.metadata or {}).get("lfs_oid") or (left.metadata or {}).get("oid")
        right_oid = (right.metadata or {}).get("lfs_oid") or (right.metadata or {}).get("oid")
        if left_oid and right_oid:
            target = lfs_matches if left_oid == right_oid else lfs_mismatches
            target.append(path if target is lfs_matches else {"path": path, "left_oid": left_oid, "right_oid": right_oid})
    return {
        "added_files": sorted(right_paths - left_paths),
        "removed_files": sorted(left_paths - right_paths),
        "common_files": len(common),
        "path_overlap_ratio": round(len(common) / len(union), 3) if union else 1.0,
        "same_name_different_path": _same_name_different_path(left_paths, right_paths),
        "changed_size_files": changed,
        "checksum_matches": checksum_matches,
        "checksum_mismatches": checksum_mismatches,
        "lfs_matches": lfs_matches,
        "lfs_mismatches": lfs_mismatches,
        "shards": _compare_shards(left_by_path, right_by_path),
    }


def _compare_cards(left, right) -> dict:
    left_norm = ((left.card.metadata or {}).get("normalized") if left.card else {}) or {}
    right_norm = ((right.card.metadata or {}).get("normalized") if right.card else {}) or {}
    left_keys = set(left_norm)
    right_keys = set(right_norm)
    semantic_keys = sorted({"license", "pipeline_tag", "library_name", "language", "datasets", "base_model"} & (left_keys | right_keys))
    semantic_delta = {key: {"left": left_norm.get(key), "right": right_norm.get(key)} for key in semantic_keys if left_norm.get(key) != right_norm.get(key)}
    return {
        "left_has_card": left.has_card,
        "right_has_card": right.has_card,
        "normalized_left": left_norm,
        "normalized_right": right_norm,
        "license_changed": (left.info.license or None) != (right.info.license or None),
        "shared_card_keys": sorted(left_keys & right_keys),
        "different_card_keys": {"left_only": sorted(left_keys - right_keys), "right_only": sorted(right_keys - left_keys)},
        "semantic_delta": semantic_delta,
    }


def _compare_formats(left, right, *, include_deep: bool = False) -> dict:
    left_formats = left.weight_formats or {}
    right_formats = right.weight_formats or {}
    keys = sorted(set(left_formats) | set(right_formats))
    result = {
        "left_weight_formats": left_formats,
        "right_weight_formats": right_formats,
        "format_delta": {key: (left_formats.get(key, 0), right_formats.get(key, 0)) for key in keys if left_formats.get(key, 0) != right_formats.get(key, 0)},
    }
    if include_deep:
        result["left_deep"] = (left.metadata or {}).get("deep")
        result["right_deep"] = (right.metadata or {}).get("deep")
    if include_deep:
        result["semantic"] = {
            "both_have_config": left.has_config and right.has_config,
            "both_have_tokenizer": left.has_tokenizer and right.has_tokenizer,
            "both_have_card": left.has_card and right.has_card,
            "config": _semantic_file_presence(left.files, right.files, ("config.json", "generation_config.json", "params.json")),
            "tokenizer": _semantic_file_presence(left.files, right.files, ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt", "merges.txt")),
            "card": _semantic_card_presence(left, right),
        }
    return result


def _semantic_file_presence(left_files, right_files, names) -> dict:
    left = sorted(f.path for f in left_files if f.path.rsplit("/", 1)[-1] in names)
    right = sorted(f.path for f in right_files if f.path.rsplit("/", 1)[-1] in names)
    return {"left": left, "right": right, "matches": bool(left) and left == right}


def _semantic_card_presence(left, right) -> dict:
    left_norm = ((left.card.metadata or {}).get("normalized") if left.card else {}) or {}
    right_norm = ((right.card.metadata or {}).get("normalized") if right.card else {}) or {}
    keys = sorted(set(left_norm) | set(right_norm))
    return {"shared_keys": sorted(set(left_norm) & set(right_norm)), "delta": {k: {"left": left_norm.get(k), "right": right_norm.get(k)} for k in keys if left_norm.get(k) != right_norm.get(k)}}


def _same_name_different_path(left_paths, right_paths) -> list[dict]:
    left_by_name = {}
    for path in left_paths:
        left_by_name.setdefault(PurePosixPath(path).name, set()).add(path)
    right_by_name = {}
    for path in right_paths:
        right_by_name.setdefault(PurePosixPath(path).name, set()).add(path)
    matches = []
    for name in sorted(set(left_by_name) & set(right_by_name)):
        left_only = sorted(left_by_name[name] - right_by_name[name])
        right_only = sorted(right_by_name[name] - left_by_name[name])
        if left_only and right_only:
            matches.append({"name": name, "left_paths": left_only, "right_paths": right_only})
    return matches


def _compare_shards(left_by_path, right_by_path) -> dict:
    def signature(items):
        sizes = [f.size or 0 for f in items.values() if _is_weight_path(f.path)]
        return {"count": len(sizes), "total_size": sum(sizes), "size_pattern": sorted(Counter(sizes).items())}
    left = signature(left_by_path)
    right = signature(right_by_path)
    return {"left": left, "right": right, "matches": left == right, "index_files": _index_files(left_by_path, right_by_path)}


def _index_files(left_by_path, right_by_path) -> dict:
    suffixes = (".safetensors.index.json", ".bin.index.json")
    left = sorted(p for p in left_by_path if p.lower().endswith(suffixes))
    right = sorted(p for p in right_by_path if p.lower().endswith(suffixes))
    return {"left": left, "right": right, "matches": left == right}


def _is_weight_path(path: str) -> bool:
    return path.lower().endswith((".safetensors", ".bin", ".pt", ".pth", ".ckpt", ".gguf", ".onnx", ".h5", ".msgpack"))


def _print_detail_summary(summary: dict) -> None:
    if "files" in summary:
        files = summary["files"]
        print("File diff:")
        print(f"  Added:        {len(files['added_files'])}")
        print(f"  Removed:      {len(files['removed_files'])}")
        print(f"  Common:       {files['common_files']}")
        print(f"  Size changed: {len(files['changed_size_files'])}")
    if "card" in summary:
        card = summary["card"]
        print("Card diff:")
        print(f"  License changed: {card['license_changed']}")
        if card["shared_card_keys"]:
            print(f"  Shared keys:      {', '.join(card['shared_card_keys'])}")
    if "formats" in summary:
        formats = summary["formats"]
        print("Format diff:")
        if formats["format_delta"]:
            for key, values in formats["format_delta"].items():
                print(f"  - {key}: {values[0]} vs {values[1]}")
        else:
            print("  No weight format differences")


__all__ = [name for name in globals() if not name.startswith("_")]
