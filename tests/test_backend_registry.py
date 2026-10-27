"""Unit tests for runtime backend registry."""

import pytest

from modely.backend_registry import (
    BackendUnavailableError,
    UnknownSourceError,
    select_backend,
)


def test_select_backend_auto_prefers_hf_sdk():
    backend = select_backend("hf", "files")

    assert backend.name == "hf-sdk"


def test_select_backend_accepts_explicit_name():
    backend = select_backend("github", "single_file", backend="github-http")

    assert backend.name == "github-http"


def test_select_backend_rejects_wrong_source():
    with pytest.raises(Exception, match="not 'github'"):
        select_backend("github", "files", backend="hf-sdk")


def test_select_backend_lightweight_modelscope_uses_http():
    backend = select_backend("ms", "snapshot", backend="lightweight")

    assert backend.name == "modelscope-lightweight"


def test_select_backend_official_requires_available_extra(monkeypatch):
    import modely.backend_registry as registry

    registry._register_builtins()
    monkeypatch.setattr(registry._BACKENDS["modelscope-official"], "available", False)

    with pytest.raises(BackendUnavailableError):
        select_backend("ms", "snapshot", backend="official")


def test_select_backend_reports_unsupported_operation():
    with pytest.raises(UnknownSourceError):
        select_backend("github", "checksum", backend="github-http")
