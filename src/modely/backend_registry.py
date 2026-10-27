"""Compatibility facade — delegates to :mod:`modely.application.backend_registry`."""

from __future__ import annotations

from .application.backend_registry import *  # noqa: F401,F403
from .application.backend_registry import _BACKENDS, _register_builtins  # noqa: F401
