"""Optional adapter for the official ModelScope SDK."""

from pathlib import Path
from typing import List, Optional, Union


def is_available() -> bool:
    """Return True when the official ModelScope SDK can be imported."""
    try:
        import modelscope  # noqa: F401
    except ImportError:
        return False
    return True


def _missing_sdk_error() -> ImportError:
    return ImportError(
        "Official ModelScope SDK is not installed. "
        "Install it with: pip install 'modely-ai[modelscope]'"
    )


def _import_snapshot_download():
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except ImportError as nested_exc:
            raise _missing_sdk_error() from nested_exc
    return snapshot_download


def _import_file_downloads():
    try:
        from modelscope.hub.file_download import dataset_file_download, model_file_download
    except ImportError as exc:
        raise _missing_sdk_error() from exc
    return model_file_download, dataset_file_download


def _cache_dir(cache_dir: Optional[Union[str, Path]]) -> Optional[str]:
    if cache_dir is None:
        return None
    return str(cache_dir)


def _filter_none(kwargs):
    return {key: value for key, value in kwargs.items() if value is not None}


def model_file_download(
    model_id: str,
    file_path: str,
    revision: Optional[str] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    """Download a model file through the official ModelScope SDK."""
    official_model_file_download, _ = _import_file_downloads()
    kwargs = _filter_none(
        {
            "model_id": model_id,
            "file_path": file_path,
            "revision": revision,
            "cache_dir": _cache_dir(cache_dir),
            "local_dir": local_dir,
            "token": token,
        }
    )
    return official_model_file_download(**kwargs)


def dataset_file_download(
    dataset_id: str,
    file_path: str,
    revision: Optional[str] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    """Download a dataset file through the official ModelScope SDK."""
    _, official_dataset_file_download = _import_file_downloads()
    kwargs = _filter_none(
        {
            "dataset_id": dataset_id,
            "file_path": file_path,
            "revision": revision,
            "cache_dir": _cache_dir(cache_dir),
            "local_dir": local_dir,
            "token": token,
        }
    )
    return official_dataset_file_download(**kwargs)


def snapshot_download(
    repo_id: str,
    repo_type: str = "model",
    revision: Optional[str] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    local_dir: Optional[str] = None,
    token: Optional[str] = None,
    allow_patterns: Optional[List[str]] = None,
    ignore_patterns: Optional[List[str]] = None,
) -> str:
    """Download a repository snapshot through the official ModelScope SDK."""
    official_snapshot_download = _import_snapshot_download()
    kwargs = _filter_none(
        {
            "model_id": repo_id,
            "repo_id": repo_id,
            "repo_type": repo_type,
            "revision": revision,
            "cache_dir": _cache_dir(cache_dir),
            "local_dir": local_dir,
            "token": token,
            "allow_patterns": allow_patterns,
            "ignore_patterns": ignore_patterns,
        }
    )

    # The SDK has used different parameter names across versions. Prefer the
    # modern superset, then retry with the common model_id-only signature.
    try:
        return official_snapshot_download(**kwargs)
    except TypeError:
        retry_kwargs = dict(kwargs)
        retry_kwargs.pop("repo_id", None)
        retry_kwargs.pop("repo_type", None)
        return official_snapshot_download(**retry_kwargs)
