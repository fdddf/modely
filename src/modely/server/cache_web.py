"""Internal package facade for :mod:`modely.server.cache_web_ui`.

The flat module ``modely.cache_web`` remains the compatibility surface; this module
re-exports from the canonical implementation so new package paths are also available.
"""

from __future__ import annotations

from .cache_web_ui import *  # noqa: F401,F403
