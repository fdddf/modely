"""Internal package facade for :mod:`modely.backends`.

The flat module remains the compatibility and monkeypatch surface; this module
re-exports it so new package paths do not duplicate implementation.
"""

from __future__ import annotations

from ..application.backends import *  # noqa: F401,F403
