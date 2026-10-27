"""Internal package facade for :mod:`modely.resolve`.

The flat module remains the compatibility and monkeypatch surface; this module
re-exports it so new package paths do not duplicate implementation.
"""

from __future__ import annotations

from ..resolve import *  # noqa: F401,F403
