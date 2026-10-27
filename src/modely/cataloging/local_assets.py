"""Internal package facade for :mod:`modely.local`.

The flat module remains the compatibility and monkeypatch surface; this module
re-exports it so new package paths do not duplicate implementation.
"""

from __future__ import annotations

from .local_analysis import *  # noqa: F401,F403
