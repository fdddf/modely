"""Unit tests for unified resource detail helpers."""

from modely.detail import get_resource_detail, print_resource_detail
from modely.types import AssetAnalysis, AssetCard, FileSummary, RepoInfo


def test_get_resource_detail_reuses_one_analysis(monkeypatch):
    info = RepoInfo("hf", "model", "org/model", url="https://huggingface.co/org/model", license="mit")
    summary = FileSummary(total_files=2, selected_files=1, total_size=20, selected_size=10, categories={"config": 1})
    card = AssetCard("hf", "model", "org/model", text="# card")
    analysis = AssetAnalysis(info=info, summary=summary, card=card, warnings=["warn"])
    calls = []

    def fake_analyze(*args, **kwargs):
        calls.append((args, kwargs))
        return analysis

    monkeypatch.setattr("modely.application.detail.analyze_resource", fake_analyze)

    detail = get_resource_detail("org/model", source="hf", repo_type="model")

    assert len(calls) == 1
    assert detail["info"]["repo_id"] == "org/model"
    assert detail["summary"]["selected_files"] == 1
    assert detail["score"]["grade"] == "F"
    assert detail["scan"]["risk_level"] == "medium"
    assert detail["commands"]["get"] == "modely-ai get org/model --source hf --repo-type model"


def test_print_resource_detail_outputs_human_summary(capsys):
    detail = {
        "info": {"source": "hf", "repo_type": "dataset", "repo_id": "org/data", "url": "https://huggingface.co/datasets/org/data"},
        "summary": {"selected_files": 2, "total_files": 3, "selected_size": 10, "total_size": 20},
        "score": {"score": 90, "grade": "A"},
        "scan": {"risk_level": "low"},
        "warnings": [],
        "commands": {"get": "modely-ai get org/data --source hf --repo-type dataset"},
    }

    print_resource_detail(detail)

    output = capsys.readouterr().out
    assert "Repo type:     dataset" in output
    assert "Score:         90/100 (A)" in output
    assert "modely-ai get org/data" in output
