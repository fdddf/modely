"""Unit tests for asset analysis."""

from modely.analyze import analyze_resource, deep_file_analysis
from modely.types import AssetCard, FileInfo, RepoInfo


def test_analyze_resource_summarizes_files(monkeypatch):
    monkeypatch.setattr("modely.analyze.get_repo_info", lambda *a, **k: RepoInfo("hf", "model", "gpt2", license="mit", tags=["nlp"]))
    monkeypatch.setattr("modely.analyze.list_repo_files", lambda *a, **k: [
        FileInfo("README.md", size=10),
        FileInfo("config.json", size=20),
        FileInfo("tokenizer.json", size=30),
        FileInfo("model.safetensors", size=1000),
    ])
    monkeypatch.setattr("modely.analyze.get_card", lambda *a, **k: AssetCard("hf", "model", "gpt2", text="# card"))

    analysis = analyze_resource("hf://models/gpt2", top_files=2)

    assert analysis.has_config is True
    assert analysis.has_tokenizer is True
    assert analysis.has_card is True
    assert analysis.weight_formats == {"safetensors": 1}
    assert analysis.largest_files[0].path == "model.safetensors"


def test_analyze_resource_deep_metadata(monkeypatch):
    monkeypatch.setattr("modely.analyze.get_repo_info", lambda *a, **k: RepoInfo("hf", "model", "gpt2", license="mit", tags=["nlp"]))
    monkeypatch.setattr("modely.analyze.list_repo_files", lambda *a, **k: [
        FileInfo("README.md", size=10),
        FileInfo("config.json", size=20),
        FileInfo("tokenizer.json", size=30),
        FileInfo("model-q4_k_m.gguf", size=1000),
        FileInfo("data/train.parquet", size=500),
    ])
    monkeypatch.setattr("modely.analyze.get_card", lambda *a, **k: AssetCard("hf", "model", "gpt2", text="# card"))

    analysis = analyze_resource("hf://models/gpt2", deep=True)

    deep = analysis.metadata["deep"]
    assert deep["formats"]["gguf"]["count"] == 1
    assert deep["formats"]["parquet"]["bytes"] == 500
    assert deep["quantization"] == {"q4_k_m": 1}
    assert "inference" in deep["recommended_profiles"]


def test_deep_file_analysis_reports_risks():
    result = deep_file_analysis([FileInfo("weights.bin", size=11_000_000_000)])

    assert "missing-license" in result["risk_flags"]
    assert "large-weights" in result["risk_flags"]
