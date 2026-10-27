"""Unit tests for multi-resource comparisons."""

from modely.compare_many import compare_many_resources, print_many_comparison


def test_compare_many_resources_summarizes_details(monkeypatch):
    def fake_detail(resource, **kwargs):
        return {
            "info": {"source": "hf", "repo_type": "model", "repo_id": resource, "license": "mit"},
            "summary": {"selected_files": 1, "total_files": 2, "selected_size": 10, "total_size": 20},
            "score": {"score": 80, "grade": "B"},
            "scan": {"risk_level": "low"},
            "warnings": [],
        }

    monkeypatch.setattr("modely.intelligence.compare_many.get_resource_detail", fake_detail)

    result = compare_many_resources(["org/a", "org/b"], source="hf")

    assert result["count"] == 2
    assert result["summary"]["sources"] == ["hf"]
    assert result["summary"]["total_size"] == 40


def test_print_many_comparison_outputs_table(capsys):
    result = {
        "resources": [{"repo_id": "org/a", "source": "hf", "repo_type": "model", "selected_files": 1, "total_files": 2, "selected_size": 10, "total_size": 20, "score": 80, "grade": "B", "risk_level": "low", "license": "mit"}]
    }

    print_many_comparison(result)

    output = capsys.readouterr().out
    assert "Resource" in output
    assert "org/a" in output
    assert "80/B" in output
