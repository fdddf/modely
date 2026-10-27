"""Unit tests for mirror verification."""

from modely.mirror import verify_mirror
from modely.types import AssetAnalysis, ComparisonResult, FileSummary, RepoInfo


def test_verify_mirror_detects_drift(monkeypatch):
    comp = ComparisonResult(
        AssetAnalysis(RepoInfo("hf", "model", "a"), FileSummary()),
        AssetAnalysis(RepoInfo("ms", "model", "a"), FileSummary()),
        summary={"files": {"added_files": ["x"], "removed_files": [], "changed_size_files": []}, "card": {}, "formats": {}},
    )
    monkeypatch.setattr("modely.mirror.compare_resources", lambda *a, **k: comp)

    result = verify_mirror("hf://models/a", "ms://models/a")

    assert result["status"] == "drifted"
    assert "right has extra files" in result["reasons"]
