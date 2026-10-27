"""Internal package facade for :mod:`modely.backend_registry`.

The flat module remains the compatibility and monkeypatch surface; this module
re-exports it so new package paths do not duplicate implementation.
"""

from __future__ import annotations

from ..backend_registry import *  # noqa: F401,F403
