"""Unit tests for resource comparison."""

from modely.compare import compare_resources
from modely.types import AssetAnalysis, AssetCard, FileInfo, FileSummary, RepoInfo


def fake_analysis(source, repo_id, license, tags, size, files):
    return AssetAnalysis(
        info=RepoInfo(source, "model", repo_id, license=license, tags=tags),
        summary=FileSummary(total_files=files, total_size=size, selected_files=files, selected_size=size),
        has_config=True,
        has_tokenizer=True,
        has_card=True,
    )


def test_compare_resources_computes_deltas(monkeypatch):
    values = [
        fake_analysis("hf", "org/a", "mit", ["nlp", "qwen"], 100, 3),
        fake_analysis("ms", "org/a", "apache-2.0", ["nlp"], 50, 2),
    ]
    monkeypatch.setattr("modely.compare.analyze_resource", lambda *a, **k: values.pop(0))

    result = compare_resources("hf://models/org/a", "ms://models/org/a")

    assert result.same_license is False
    assert result.size_delta == 50
    assert result.file_count_delta == 1
    assert result.shared_tags == ["nlp"]
    assert result.different_tags["left_only"] == ["qwen"]


def test_compare_resources_can_include_file_card_and_format_details(monkeypatch):
    left = fake_analysis("hf", "org/a", "mit", ["nlp"], 100, 2)
    left.files = [FileInfo("config.json", size=10), FileInfo("model.safetensors", size=90)]
    left.weight_formats = {"safetensors": 1}
    left.card = AssetCard("hf", "model", "org/a", text="# card", metadata={"normalized": {"license": "mit", "tags": ["nlp"]}})
    left.metadata = {"deep": {"has_safetensors": True}}
    right = fake_analysis("ms", "org/a", "apache-2.0", ["nlp"], 120, 2)
    right.files = [FileInfo("config.json", size=20), FileInfo("model.gguf", size=100)]
    right.weight_formats = {"gguf": 1}
    right.card = AssetCard("ms", "model", "org/a", text="# card", metadata={"normalized": {"license": "apache-2.0"}})
    right.metadata = {"deep": {"has_gguf": True}}
    values = [left, right]
    monkeypatch.setattr("modely.compare.analyze_resource", lambda *a, **k: values.pop(0))

    result = compare_resources("hf://models/org/a", "ms://models/org/a", include_files=True, include_card=True, include_formats=True, deep=True)

    assert result.summary["files"]["added_files"] == ["model.gguf"]
    assert result.summary["files"]["removed_files"] == ["model.safetensors"]
    assert result.summary["files"]["changed_size_files"][0]["path"] == "config.json"
    assert result.summary["card"]["license_changed"] is True
    assert result.summary["formats"]["format_delta"] == {"gguf": (0, 1), "safetensors": (1, 0)}
    assert result.summary["formats"]["left_deep"] == {"has_safetensors": True}
