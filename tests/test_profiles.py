"""Unit tests for download profiles."""

import pytest

from modely.profiles import resolve_download_profile


def test_full_profile_keeps_explicit_patterns():
    include, exclude = resolve_download_profile("full", ["*.json"], ["*.bin"])
    assert include == ["*.json"]
    assert exclude == ["*.bin"]


def test_minimal_profile_adds_include_patterns():
    include, exclude = resolve_download_profile("minimal", None, None)
    assert "README*" in include
    assert "tokenizer*" in include
    assert exclude is None


def test_no_weights_profile_adds_excludes_and_merges_explicit():
    include, exclude = resolve_download_profile("no-weights", ["*.json"], ["custom.bin"])
    assert include == ["*.json"]
    assert "*.safetensors" in exclude
    assert "custom.bin" in exclude


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        resolve_download_profile("unknown", None, None)
