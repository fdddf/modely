"""Download profile presets for modely-ai."""

from __future__ import annotations

from typing import List, Optional, Tuple

PROFILES = {
    "full": {"include": None, "exclude": None, "description": "Download all selected files."},
    "minimal": {
        "include": ["README*", "*.md", "config*.json", "tokenizer*", "vocab.*", "merges.txt", "*.model", "*.yaml", "*.yml"],
        "exclude": None,
        "description": "Metadata, config, and tokenizer files only.",
    },
    "no-weights": {
        "include": None,
        "exclude": ["*.bin", "*.safetensors", "*.pt", "*.pth", "*.ckpt", "*.onnx", "*.gguf", "*.h5", "*.msgpack"],
        "description": "Exclude common large model weight formats.",
    },
    "inference": {
        "include": ["README*", "*.md", "config*.json", "tokenizer*", "vocab.*", "merges.txt", "*.model", "*.safetensors", "*.gguf", "*.json"],
        "exclude": ["*.pt", "*.pth", "*.ckpt", "*.h5", "*.msgpack"],
        "description": "Config/tokenizer files plus common inference weights.",
    },
}


def resolve_download_profile(profile: Optional[str], include: Optional[List[str]], exclude: Optional[List[str]]) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """Merge a named download profile with explicit include/exclude patterns."""
    if not profile or profile == "full":
        return include, exclude
    if profile not in PROFILES:
        raise ValueError(f"Unknown download profile: {profile}")
    preset = PROFILES[profile]
    merged_include = _merge_patterns(preset.get("include"), include)
    merged_exclude = _merge_patterns(preset.get("exclude"), exclude)
    return merged_include, merged_exclude


def _merge_patterns(base, extra):
    patterns = []
    for values in (base, extra):
        if values:
            patterns.extend(values)
    return patterns or None


__all__ = ["PROFILES", "resolve_download_profile"]
