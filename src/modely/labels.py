"""Compatibility facade for local asset labels."""

from __future__ import annotations

from .cataloging.labels import *  # noqa: F401,F403
from .cataloging.labels import (
    export_project as _export_project,
    get_asset_record as _get_asset_record,
    list_asset_metadata as _list_asset_metadata,
    load_asset_metadata as _load_asset_metadata,
    save_asset_metadata as _save_asset_metadata,
    update_asset_record as _update_asset_record,
)
from .cataloging.labels import metadata_path


def load_asset_metadata():
    return _load_asset_metadata(metadata_path_func=metadata_path)


def save_asset_metadata(data: dict) -> None:
    return _save_asset_metadata(data, metadata_path_func=metadata_path)


def get_asset_record(*args, **kwargs):
    kwargs.setdefault("metadata_path_func", metadata_path)
    return _get_asset_record(*args, **kwargs)


def update_asset_record(*args, **kwargs):
    kwargs.setdefault("metadata_path_func", metadata_path)
    return _update_asset_record(*args, **kwargs)


def list_asset_metadata(*args, **kwargs):
    kwargs.setdefault("metadata_path_func", metadata_path)
    return _list_asset_metadata(*args, **kwargs)


def export_project(*args, **kwargs):
    kwargs.setdefault("metadata_path_func", metadata_path)
    return _export_project(*args, **kwargs)
