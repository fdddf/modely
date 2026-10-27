"""Unit tests for modely URI parsing."""

import pytest

from modely.uri import concrete_repo_type, format_modely_uri, normalize_repo_type, parse_modely_uri, repo_type_candidates


def test_parse_hf_model_uri():
    ref = parse_modely_uri("hf://models/gpt2")
    assert ref.source == "hf"
    assert ref.repo_type == "model"
    assert ref.repo_id == "gpt2"


def test_parse_hf_dataset_uri_with_query():
    ref = parse_modely_uri("hf://datasets/google/fleurs?revision=main&file=README.md")
    assert ref.source == "hf"
    assert ref.repo_type == "dataset"
    assert ref.repo_id == "google/fleurs"
    assert ref.revision == "main"
    assert ref.path == "README.md"


def test_parse_ms_uri():
    ref = parse_modely_uri("ms://models/owner/model")
    assert ref.source == "ms"
    assert ref.repo_type == "model"
    assert ref.repo_id == "owner/model"


def test_parse_github_uri():
    ref = parse_modely_uri("github://owner/repo?revision=main")
    assert ref.source == "github"
    assert ref.repo_type == "tool"
    assert ref.repo_id == "owner/repo"
    assert ref.revision == "main"


def test_parse_github_https_url():
    ref = parse_modely_uri("https://github.com/d2l-ai/d2l-zh.git")
    assert ref.source == "github"
    assert ref.repo_type == "tool"
    assert ref.repo_id == "d2l-ai/d2l-zh"


def test_plain_repo_uses_explicit_source():
    ref = parse_modely_uri("owner/repo", source="github")
    assert ref.source == "github"
    assert ref.repo_type == "tool"
    assert ref.repo_id == "owner/repo"


def test_normalize_repo_type_aliases():
    assert normalize_repo_type("models", "hf") == "model"
    assert normalize_repo_type("datasets", "ms") == "dataset"
    assert normalize_repo_type("models", "github") == "tool"


def test_auto_repo_type_helpers():
    assert normalize_repo_type("auto", "hf") == "auto"
    assert concrete_repo_type("auto", "hf") == "model"
    assert concrete_repo_type("auto", "github") == "tool"
    assert repo_type_candidates("auto", "hf") == ["model", "dataset"]
    assert repo_type_candidates("auto", "github") == ["tool"]


def test_invalid_source_raises():
    with pytest.raises(ValueError):
        parse_modely_uri("unknown://models/repo")


def test_format_modely_uri_roundtrip():
    ref = parse_modely_uri("hf://models/gpt2?revision=main&file=config.json")
    assert format_modely_uri(ref) == "hf://models/gpt2?revision=main&file=config.json"
