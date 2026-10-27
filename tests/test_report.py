"""Unit tests for resource reports."""

from modely.report import create_resource_report


def test_markdown_report(monkeypatch):
    monkeypatch.setattr("modely.report.doctor_resource", lambda *a, **k: {"query": "x", "recommended": "hf://models/x", "score": {"score": 90, "grade": "A"}, "scan": {"risk_level": "low"}, "warnings": []})

    text = create_resource_report("x", format="markdown")

    assert "# modely report" in text
    assert "hf://models/x" in text


def test_html_report(monkeypatch):
    monkeypatch.setattr("modely.report.doctor_resource", lambda *a, **k: {"query": "x", "recommended": "hf://models/x", "score": {}, "scan": {}, "warnings": []})

    assert "<!doctype html>" in create_resource_report("x", format="html")


def test_report_supports_local_path(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "weights.pkl").write_text("pickle")

    text = create_resource_report(str(tmp_path), format="markdown")

    assert f"- Recommended: `{tmp_path}`" in text
    assert "- Risk: high" in text
