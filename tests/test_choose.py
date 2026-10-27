"""Unit tests for choose helpers."""

from modely.choose import choose_resource
from modely.types import AssetAnalysis, AssetScore, FileSummary, RepoInfo, ScanResult, ScoreBreakdown


class FakeCandidate:
    def __init__(self, uri, source, confidence):
        self.modely_uri = uri
        self.repo_id = uri.rsplit("/", 1)[-1]
        self.source = source
        self.confidence = confidence
        self.signals = ["name-exact"]
        self.result = {}


class FakeResolve:
    warnings = []

    def __init__(self):
        self.candidates = [
            FakeCandidate("hf://models/org/a", "hf", 0.8),
            FakeCandidate("ms://models/org/a", "ms", 0.7),
        ]

    def to_dict(self):
        return {"candidates": [c.modely_uri for c in self.candidates]}


def test_choose_resource_ranks_candidates(monkeypatch):
    monkeypatch.setattr("modely.intelligence.decision.resolve_resource", lambda *a, **k: FakeResolve())
    monkeypatch.setattr("modely.intelligence.decision.score_resource", lambda uri, **k: AssetScore(uri, 80 if uri.startswith("hf") else 95, "A", ScoreBreakdown()))
    monkeypatch.setattr("modely.intelligence.decision.scan_resource", lambda uri, **k: ScanResult(uri, "low", analysis=AssetAnalysis(RepoInfo("hf", "model", "org/a"), FileSummary())))

    result = choose_resource("a")

    assert result["recommended"]["uri"] == "ms://models/org/a"
    assert len(result["candidates"]) == 2
