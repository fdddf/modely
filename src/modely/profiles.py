"""Compatibility facade for download profile presets."""

from __future__ import annotations

from .application.download_profiles import PROFILES, resolve_download_profile

__all__ = ["PROFILES", "resolve_download_profile"]
