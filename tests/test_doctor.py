"""Unit tests for doctor reports."""

from modely.doctor import doctor_resource, print_doctor_report
from modely.types import AssetAnalysis, AssetScore, FileSummary, RepoInfo, ScanResult, ScoreBreakdown


class FakeCandidate:
    def __init__(self):
        self.modely_uri = "hf://models/org/model"
        self.repo_id = "org/model"


class FakeResolve:
    warnings = []
    candidates = [FakeCandidate()]

    def to_dict(self):
        return {"candidates": [{"modely_uri": "hf://models/org/model"}]}


def test_doctor_resource_uses_top_resolve_candidate(monkeypatch):
    monkeypatch.setattr("modely.intelligence.doctor.resolve_resource", lambda *a, **k: FakeResolve())
    monkeypatch.setattr("modely.intelligence.doctor.score_resource", lambda *a, **k: AssetScore("r", 90, "A", ScoreBreakdown()))
    monkeypatch.setattr("modely.intelligence.doctor.scan_resource", lambda *a, **k: ScanResult("r", "low", analysis=AssetAnalysis(RepoInfo("hf", "model", "org/model"), FileSummary())))

    result = doctor_resource("model")

    assert result["recommended"] == "hf://models/org/model"
    assert result["score"]["score"] == 90
    assert result["scan"]["risk_level"] == "low"


def test_print_doctor_json(capsys):
    print_doctor_report({"query": "x", "recommended": None, "warnings": [], "next_steps": []}, as_json=True)
    assert '"query": "x"' in capsys.readouterr().out
