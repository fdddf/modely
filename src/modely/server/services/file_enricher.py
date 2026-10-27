"""File metadata enrichment for cached assets.

Reads files from the local modely cache and returns enriched metadata
including MIME type, file-type classification, and SHA-256 checksum.
All heavy computation (SHA-256) is skipped for large files.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
from typing import Any

# -- MIME type overrides for ML-specific extensions ------------------------

_MIME_OVERRIDES: dict[str, str] = {
    "safetensors": "application/octet-stream",
    "gguf": "application/octet-stream",
    "onnx": "application/octet-stream",
    "pth": "application/octet-stream",
    "pt": "application/octet-stream",
    "bin": "application/octet-stream",
    "msgpack": "application/octet-stream",
    "h5": "application/octet-stream",
    "ckpt": "application/octet-stream",
    "pb": "application/octet-stream",
    "tflite": "application/octet-stream",
    "mar": "application/octet-stream",
    "pickle": "application/octet-stream",
    "joblib": "application/octet-stream",
    "npy": "application/octet-stream",
    "npz": "application/octet-stream",
}

# -- File-type classification -----------------------------------------------

_CARD_EXTENSIONS = {".md", ".rst", ".txt"}
_CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env"}
_TOKENIZER_EXTENSIONS = {".json", ".model", ".vocab"}
_WEIGHT_EXTENSIONS = {".safetensors", ".gguf", ".bin", ".pth", ".pt", ".h5", ".ckpt", ".onnx", ".pb", ".tflite", ".mar"}
_METADATA_EXTENSIONS = {".lock", ".modely", ".csv", ".tsv", ".jsonl"}


def classify_file_type(name: str) -> str:
    """Classify a file by its extension into a semantic category.

    Returns one of: ``card``, ``config``, ``tokenizer``, ``safetensors``,
    ``gguf``, ``weights``, ``metadata``, ``other``.
    """
    base = os.path.basename(name).lower()
    ext = os.path.splitext(base)[1]

    # Special-case known tokenizer/config files
    base_no_ext = os.path.splitext(base)[0]
    if base_no_ext.startswith("tokenizer"):
        return "tokenizer"
    if base_no_ext in ("config", "preprocessor_config", "generation_config"):
        return "config"

    if ext == ".md" or base in ("readme", "readme.md", "readme.rst", "readme.txt"):
        return "card"
    if ext == ".safetensors":
        return "safetensors"
    if ext == ".gguf":
        return "gguf"
    if ext in _WEIGHT_EXTENSIONS:
        return "weights"
    if ext in _CONFIG_EXTENSIONS:
        return "config"
    if ext in _TOKENIZER_EXTENSIONS:
        return "tokenizer"
    if ext in _METADATA_EXTENSIONS:
        return "metadata"
    return "other"


# -- MIME type detection ----------------------------------------------------

def detect_mime_type(name: str) -> str | None:
    """Detect the MIME type for *name*, using ``mimetypes`` plus ML overrides."""
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(name)
    return mime


# -- SHA-256 computation ----------------------------------------------------

_SHA256_CHUNK_SIZE = 64 * 1024  # 64 KB per read
_SHA256_MAX_SIZE = 10 * 1024 * 1024  # skip hashing for files > 10 MB


def compute_sha256(file_path: str) -> str | None:
    """Compute the SHA-256 hex digest of *file_path*.

    Returns ``None`` when the file is larger than 10 MB or cannot be read.
    """
    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        return None
    if file_size > _SHA256_MAX_SIZE:
        return None
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(_SHA256_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# -- Main entry point -------------------------------------------------------

def enrich_file_item(file_item: dict[str, Any], local_dir: str) -> dict[str, Any]:
    """Enrich a raw cache file dict with computed metadata.

    *file_item* is expected to contain at least ``"name"`` and ``"size"``
    (as returned by ``modely.common.cache.list_cache(detail=True)``).

    *local_dir* is the filesystem path to the cached revision directory.

    Returns a dict suitable for ``AssetFileResponse``.
    """
    name = file_item.get("name", "")
    size = file_item.get("size", 0)

    full_path = os.path.join(local_dir, name) if local_dir else ""

    file_type = classify_file_type(name)
    mime_type = detect_mime_type(name)
    sha256 = compute_sha256(full_path) if os.path.isfile(full_path) else None

    # File modification time (ISO 8601)
    mtime: str | None = None
    if full_path and os.path.isfile(full_path):
        try:
            mtime = _format_mtime(os.path.getmtime(full_path))
        except OSError:
            pass

    return {
        "path": name,
        "size": size,
        "sha256": sha256,
        "file_type": file_type,
        "mime_type": mime_type,
        "mtime": mtime,
        "metadata": {},
    }


def _format_mtime(timestamp: float) -> str:
    """Format a Unix mtime into an ISO-8601 string."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


__all__ = ["classify_file_type", "compute_sha256", "detect_mime_type", "enrich_file_item"]
