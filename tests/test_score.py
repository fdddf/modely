"""Unit tests for asset health scoring."""

import json

from modely.score import print_asset_score, score_path, score_resource
from modely.types import AssetAnalysis, FileInfo, FileSummary, RepoInfo


def _analysis(**overrides):
    files = overrides.pop("files", [
        FileInfo("README.md", size=10, sha256="a"),
        FileInfo("config.json", size=20, sha256="b"),
        FileInfo("tokenizer.json", size=30, sha256="c"),
        FileInfo("model.safetensors", size=1000, sha256="d"),
    ])
    info = overrides.pop("info", RepoInfo(
        "hf",
        "model",
        "org/model",
        url="https://huggingface.co/org/model",
        author="org",
        revision="main",
        downloads=1_000_000,
        likes=2_000,
        forks=10,
        created_at="2023-01-01",
        last_modified="2024-01-01",
        description="A useful model",
        license="mit",
        tags=["nlp"],
    ))
    defaults = {
        "info": info,
        "summary": FileSummary(total_files=len(files), selected_files=len(files), selected_size=sum(f.size for f in files)),
        "files": files,
        "weight_formats": {"safetensors": 1},
        "has_config": True,
        "has_tokenizer": True,
        "has_card": True,
        "metadata": {"deep": {"formats": {"safetensors": {"count": 1, "bytes": 1000}}, "risk_flags": [], "recommended_profiles": ["minimal"]}},
    }
    defaults.update(overrides)
    return AssetAnalysis(**defaults)


def test_score_complete_model_gets_high_grade(monkeypatch):
    monkeypatch.setattr("modely.score.analyze_resource", lambda *a, **k: _analysis())

    result = score_resource("hf://models/org/model")

    assert result.grade == "A"
    assert result.score >= 85
    assert "asset appears complete" in result.strengths
    assert "checksum metadata available" in result.strengths


def test_score_missing_metadata_lowers_score(monkeypatch):
    analysis = _analysis(
        info=RepoInfo("hf", "model", "org/model", license=None),
        has_card=False,
        has_config=False,
        has_tokenizer=False,
        files=[FileInfo("weights.bin", size=100)],
        weight_formats={"bin": 1},
        metadata={"deep": {"formats": {"bin": {"count": 1, "bytes": 100}}, "risk_flags": []}},
    )
    monkeypatch.setattr("modely.score.analyze_resource", lambda *a, **k: analysis)

    result = score_resource("hf://models/org/model")

    assert result.score < 70
    assert any("missing-license" in risk for risk in result.risks)
    assert result.recommendations


def test_score_risky_files_penalize_safety(monkeypatch):
    safe = _analysis()
    risky = _analysis(files=[FileInfo("weights.pkl", size=100, sha256="x")], weight_formats={})
    monkeypatch.setattr("modely.score.analyze_resource", lambda *a, **k: safe)
    safe_result = score_resource("hf://models/org/model")
    monkeypatch.setattr("modely.score.analyze_resource", lambda *a, **k: risky)
    risky_result = score_resource("hf://models/org/model")

    assert risky_result.breakdown.safety < safe_result.breakdown.safety
    assert any("pickle-artifact" in risk for risk in risky_result.risks)


def test_score_json_output(monkeypatch, capsys):
    monkeypatch.setattr("modely.score.analyze_resource", lambda *a, **k: _analysis())

    print_asset_score(score_resource("hf://models/org/model"), as_json=True)
    parsed = json.loads(capsys.readouterr().out)

    assert parsed["resource"] == "hf://models/org/model"
    assert parsed["breakdown"]["completeness"] > 0


def test_score_human_output(monkeypatch, capsys):
    monkeypatch.setattr("modely.score.analyze_resource", lambda *a, **k: _analysis())

    print_asset_score(score_resource("hf://models/org/model"))
    out = capsys.readouterr().out

    assert "Score:" in out
    assert "Breakdown:" in out
    assert "Strengths:" in out


def test_score_path_local_model(tmp_path):
    (tmp_path / "README.md").write_text("# model")
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "tokenizer.json").write_text("{}")
    (tmp_path / "model.safetensors").write_text("weights")

    result = score_path(str(tmp_path))

    assert result.resource == str(tmp_path)
    assert result.breakdown.completeness > 0
