"""Unit tests for repository info auto resolution."""

import pytest

from modely.info import get_repo_info, resolve_repo_ref
from modely.types import RepoInfo


def test_get_repo_info_auto_falls_back_to_hf_dataset(monkeypatch):
    calls = []

    def fake_hf_info(repo_id, *, repo_type, **kwargs):
        calls.append(repo_type)
        if repo_type == "model":
            raise Exception("Repository Not Found")
        return RepoInfo("hf", "dataset", repo_id)

    monkeypatch.setattr("modely.hf.get_repo_info", fake_hf_info)

    info = get_repo_info("HennyPr/ps2_hf2", repo_type="auto")

    assert info.repo_type == "dataset"
    assert calls == ["model", "dataset"]


def test_get_repo_info_explicit_uri_does_not_fallback(monkeypatch):
    calls = []

    def fake_hf_info(repo_id, *, repo_type, **kwargs):
        calls.append(repo_type)
        raise Exception("model missing")

    monkeypatch.setattr("modely.hf.get_repo_info", fake_hf_info)

    with pytest.raises(Exception, match="model missing"):
        get_repo_info("hf://models/HennyPr/ps2_hf2", repo_type="auto")

    assert calls == ["model"]


def test_resolve_repo_ref_returns_concrete_auto_type(monkeypatch):
    monkeypatch.setattr("modely.info.get_repo_info", lambda *a, **k: RepoInfo("hf", "dataset", "org/data", revision="main"))

    ref = resolve_repo_ref("org/data", repo_type="auto")

    assert ref.source == "hf"
    assert ref.repo_type == "dataset"
    assert ref.repo_id == "org/data"
