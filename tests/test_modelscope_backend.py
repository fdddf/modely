"""Unit tests for ModelScope backend selection."""

import builtins

import pytest

from modely import modelscope as ms_mod
from modely.modelscope import official_adapter


class TestModelScopeBackendSelection:
    def test_lightweight_backend_never_uses_official(self, monkeypatch):
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)
        assert ms_mod._should_use_official_backend("lightweight") is False

    def test_auto_uses_lightweight_when_official_missing(self, monkeypatch):
        monkeypatch.setattr(official_adapter, "is_available", lambda: False)
        assert ms_mod._should_use_official_backend("auto") is False

    def test_official_backend_requires_sdk(self, monkeypatch):
        monkeypatch.setattr(official_adapter, "is_available", lambda: False)
        with pytest.raises(ImportError, match=r"modely-ai\[modelscope\]"):
            ms_mod._should_use_official_backend("official")

    def test_invalid_backend_rejected(self):
        with pytest.raises(ValueError, match="backend must be one of"):
            ms_mod._should_use_official_backend("bad")

    def test_model_file_auto_uses_official_when_available(self, monkeypatch):
        called = {}
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)

        def fake_official(**kwargs):
            called.update(kwargs)
            return "/official/config.json"

        monkeypatch.setattr(official_adapter, "model_file_download", fake_official)

        result = ms_mod.model_file_download(
            "owner/model",
            "config.json",
            revision="master",
            cache_dir="/tmp/modely-cache",
            backend="auto",
        )

        assert result == "/official/config.json"
        assert called["model_id"] == "owner/model"
        assert called["file_path"] == "config.json"
        assert called["local_dir"] == "/tmp/modely-cache/ms/models/owner--model/master"

    def test_model_file_auto_falls_back_when_official_fails(self, monkeypatch):
        called = {}
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)
        monkeypatch.setattr(
            official_adapter,
            "model_file_download",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("sdk failed")),
        )

        def fake_lightweight(**kwargs):
            called.update(kwargs)
            return "/lightweight/config.json"

        monkeypatch.setattr(ms_mod, "_lightweight_model_file_download", fake_lightweight)

        result = ms_mod.model_file_download(
            "owner/model",
            "config.json",
            revision="master",
            backend="auto",
        )

        assert result == "/lightweight/config.json"
        assert called["model_id"] == "owner/model"
        assert called["file_path"] == "config.json"

    def test_model_file_official_does_not_fallback(self, monkeypatch):
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)
        monkeypatch.setattr(
            official_adapter,
            "model_file_download",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("sdk failed")),
        )
        monkeypatch.setattr(
            ms_mod,
            "_lightweight_model_file_download",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not fallback")),
        )

        with pytest.raises(RuntimeError, match="sdk failed"):
            ms_mod.model_file_download("owner/model", "config.json", backend="official")

    def test_snapshot_auto_uses_official_when_available(self, monkeypatch):
        called = {}
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)

        def fake_official(**kwargs):
            called.update(kwargs)
            return "/official/repo"

        monkeypatch.setattr(official_adapter, "snapshot_download", fake_official)

        result = ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            revision="master",
            cache_dir="/tmp/modely-cache",
            allow_patterns=["*.json"],
            backend="auto",
        )

        assert result == "/official/repo"
        assert called["repo_id"] == "owner/model"
        assert called["allow_patterns"] == ["*.json"]
        assert called["local_dir"] == "/tmp/modely-cache/ms/models/owner--model/master"

    def test_snapshot_official_respects_local_dir(self, monkeypatch):
        called = {}
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)

        def fake_official(**kwargs):
            called.update(kwargs)
            return "/custom/repo"

        monkeypatch.setattr(official_adapter, "snapshot_download", fake_official)

        ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            revision="master",
            cache_dir="/tmp/modely-cache",
            local_dir="/custom/repo",
            backend="auto",
        )

        assert called["local_dir"] == "/custom/repo"


        called = {}
        monkeypatch.setattr(official_adapter, "is_available", lambda: True)

        def fake_lightweight(**kwargs):
            called.update(kwargs)
            return "/lightweight/repo"

        monkeypatch.setattr(ms_mod, "_lightweight_snapshot_download", fake_lightweight)

        result = ms_mod.snapshot_download(
            "owner/model",
            repo_type="model",
            revision="master",
            backend="lightweight",
        )

        assert result == "/lightweight/repo"
        assert called["repo_id"] == "owner/model"
        assert called["repo_type"] == "model"


class TestOfficialAdapter:
    def test_is_available_false_when_import_fails(self, monkeypatch):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "modelscope":
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert official_adapter.is_available() is False

    def test_filter_none_removes_none_values(self):
        assert official_adapter._filter_none({"a": 1, "b": None}) == {"a": 1}


def test_lightweight_snapshot_raises_when_model_file_list_empty(monkeypatch, tmp_path):
    class FakeApi:
        def __init__(self, token=None):
            pass
        def get_endpoint_for_read(self, *args, **kwargs):
            return "https://modelscope.cn"
        def get_valid_revision(self, *args, **kwargs):
            return "master"
        def get_cookies(self, *args, **kwargs):
            return {}
        def get_model_files(self, **kwargs):
            return []

    monkeypatch.setattr(ms_mod, "HubApi", FakeApi)

    with pytest.raises(FileNotFoundError, match="owner/name"):
        ms_mod.snapshot_download("missing-model", repo_type="model", cache_dir=str(tmp_path), backend="lightweight")
