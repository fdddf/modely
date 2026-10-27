"""Safe, read-only file preview for cached asset files.

Only text-based files are previewed.  Binary files are detected and
rejected.  Path traversal is blocked.  Content is capped at 64 KB.
"""

from __future__ import annotations

import os

# Extensions we consider safe to preview as text.
_TEXT_EXTENSIONS: set[str] = {
    ".json", ".yaml", ".yml", ".md", ".txt", ".py", ".cfg", ".toml",
    ".ini", ".env", ".modely", ".lock", ".jsonl", ".csv", ".tsv",
    ".rst", ".sh", ".bash", ".h", ".c", ".cpp", ".cc", ".js", ".ts",
    ".html", ".css", ".xml", ".sql", ".graphql", ".proto",
    ".model", ".vocab",  # tokenizer files (often JSON or text)
}

# Extensionless files we know are text.
_TEXT_BASENAMES: set[str] = {
    "license", "readme", "makefile", "dockerfile", "changelog",
    "authors", "contributing", "notice", "acknowledgements",
}

# Binary file signatures (magic bytes).
_BINARY_SIGNATURES: list[bytes] = [
    b"\x00",           # generic null byte header
    b"\x89PNG",        # PNG
    b"\xff\xd8\xff",   # JPEG
    b"GIF8",           # GIF
    b"%PDF",           # PDF
    b"PK\x03\x04",     # ZIP / DOCX / ODT / safetensors container
    b"Rar!",           # RAR
    b"\x1f\x8b\x08",   # GZIP
    b"BZh",            # BZIP2
    b"\x1f\x9d",       # compress (.Z)
]

MAX_PREVIEW_BYTES: int = 65536  # 64 KB


def get_file_preview(
    local_dir: str,
    file_path: str,
    max_bytes: int = MAX_PREVIEW_BYTES,
) -> dict:
    """Return a safe preview dict for a file inside a cached asset directory.

    Parameters
    ----------
    local_dir:
        Filesystem path to the cached revision directory.
    file_path:
        Relative file path within *local_dir*.
    max_bytes:
        Maximum bytes to read (default 64 KB).

    Returns
    -------
    dict with keys:
        - ``path`` (str)
        - ``size`` (int)
        - ``previewable`` (bool)
        - ``content`` (str | None)
        - ``content_truncated`` (bool)
        - ``encoding`` (str | None)
        - ``error`` (str | None)
    """
    base: dict = {
        "path": file_path,
        "size": 0,
        "previewable": False,
        "content": None,
        "content_truncated": False,
        "encoding": None,
        "error": None,
    }

    # -- path-traversal guard -------------------------------------------------
    local_dir_norm = os.path.normpath(os.path.abspath(local_dir))
    full_path = os.path.normpath(os.path.join(local_dir_norm, file_path))
    if not full_path.startswith(local_dir_norm + os.sep) and full_path != local_dir_norm:
        base["error"] = "Path traversal denied"
        return base

    if not os.path.isfile(full_path):
        base["error"] = "File not found"
        return base

    try:
        file_size = os.path.getsize(full_path)
    except OSError as e:
        base["error"] = str(e)
        return base
    base["size"] = file_size

    # -- extension gate -------------------------------------------------------
    ext = os.path.splitext(file_path)[1].lower()
    basename_lower = os.path.basename(file_path).lower()
    if ext not in _TEXT_EXTENSIONS and basename_lower not in _TEXT_BASENAMES:
        base["error"] = f"File type not previewable ({ext or 'no extension'})"
        return base

    # -- binary-signature gate ------------------------------------------------
    try:
        with open(full_path, "rb") as fh:
            header = fh.read(32)
    except OSError as e:
        base["error"] = str(e)
        return base

    for sig in _BINARY_SIGNATURES:
        if header.startswith(sig):
            base["error"] = "Binary file detected"
            return base

    # Null bytes in header suggest binary content.
    if b"\x00" in header:
        base["error"] = "Binary content detected (null bytes)"
        return base

    # -- read as UTF-8 --------------------------------------------------------
    try:
        with open(full_path, "r", encoding="utf-8") as fh:
            content = fh.read(max_bytes)
    except UnicodeDecodeError:
        base["error"] = "Cannot decode as UTF-8 text"
        return base
    except OSError as e:
        base["error"] = str(e)
        return base

    base["previewable"] = True
    base["content"] = content
    base["content_truncated"] = file_size > max_bytes
    base["encoding"] = "utf-8"
    return base


__all__ = ["get_file_preview"]
