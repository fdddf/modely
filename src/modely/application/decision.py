"""Internal package facade for :mod:`modely.decision`.

The flat module remains the compatibility and monkeypatch surface; this module
re-exports it so new package paths do not duplicate implementation.
"""

from __future__ import annotations

from ..intelligence.decision import *  # noqa: F401,F403
