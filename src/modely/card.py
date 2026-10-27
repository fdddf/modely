"""Compatibility facade for card helpers."""

from __future__ import annotations

from .cataloging.cards import *  # noqa: F401,F403
from .cataloging.cards import get_card as _get_card, _get_github_card, _get_hf_card, _get_ms_card


def get_card(*args, **kwargs):
    kwargs.setdefault("get_hf_card_func", _get_hf_card)
    kwargs.setdefault("get_github_card_func", _get_github_card)
    kwargs.setdefault("get_ms_card_func", _get_ms_card)
    return _get_card(*args, **kwargs)
