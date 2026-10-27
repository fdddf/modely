"""Tests for tag-based batch download helpers."""

import json
import sys

import pytest

import modely
from modely.batch import create_batch_download_plan, filter_results_by_tags, print_batch_download_result, run_batch_download
from modely.search import SearchResult


def test_filter_results_by_tags_requires_all_requested_tags():
    results = [
        SearchResult(id="org/matching", source="hf", repo_type="model", tags=["text-generation", "transformers"]),
        SearchResult(id="org/partial", source="hf", repo_type="model", tags=["text-generation"]),
        SearchResult(id="org/other", source="hf", repo_type="model", tags=["transformers", "vision"]),
    ]

    filtered = filter_results_by_tags(results, ["text-generation", "transformers"])

    assert [item.id for item in filtered] == ["org/matching"]


def test_filter_results_by_tags_matches_case_insensitively():
    results = [SearchResult(id="org/model", source="hf", repo_type="model", tags=["Text-Generation", "Transformers"])]

    filtered = filter_results_by_tags(results, ["text-generation", "TRANSFORMERS"])

    assert [item.id for item in filtered] == ["org/model"]


def test_filter_results_by_tags_rejects_empty_tags():
    with pytest.raises(ValueError, match="at least one tag"):
        filter_results_by_tags([], [])


def test_create_batch_download_plan_filters_and_limits(monkeypatch):
    def fake_search(**kwargs):
        assert kwargs["keyword"] == "qwen"
        assert kwargs["source"] == "hf"
        assert kwargs["repo_type"] == "model"
        assert kwargs["limit"] == 10
        return [
            SearchResult(id="org/one", source="hf", repo_type="model", tags=["text-generation", "transformers"]),
            SearchResult(id="org/two", source="hf", repo_type="model", tags=["text-generation", "transformers"]),
            SearchResult(id="org/skip", source="hf", repo_type="model", tags=["text-generation"]),
        ]

    monkeypatch.setattr("modely.application.batch.search", fake_search)

    plan = create_batch_download_plan("qwen", source="hf", repo_type="model", tags=["text-generation", "transformers"], limit=1, search_limit=10)

    assert plan["dry_run"] is True
    assert plan["matched_count"] == 2
    assert [item["resource"] for item in plan["downloads"]] == ["hf://models/org/one"]


def test_create_batch_download_plan_rejects_empty_filters():
    with pytest.raises(ValueError, match="Missing search filter") as exc:
        create_batch_download_plan(None, tags=[])
    message = str(exc.value)
    assert "  - keyword" in message
    assert "  - --tag TAG" in message
    assert "  - --task TASK" in message
    assert "Example:" in message


def test_create_batch_download_plan_allows_task_without_tags(monkeypatch):
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=[])],
    )

    plan = create_batch_download_plan(None, tags=[], task="text-generation")

    assert plan["tags"] == []
    assert plan["downloads"][0]["resource"] == "hf://models/org/model"

def test_create_batch_download_plan_allows_keyword_without_tags(monkeypatch):
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=[])],
    )

    plan = create_batch_download_plan("qwen", tags=[])

    assert plan["downloads"][0]["resource"] == "hf://models/org/model"


def test_create_batch_download_plan_filters_repo_type_from_all_sources(monkeypatch):
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [
            SearchResult(id="org/model", source="hf", repo_type="model", tags=[]),
            SearchResult(id="owner/tool", source="github", repo_type="tool", tags=[]),
        ],
    )

    plan = create_batch_download_plan("qwen", source="all", repo_type="model", tags=[])

    assert [item["resource"] for item in plan["downloads"]] == ["hf://models/org/model"]


def test_run_batch_download_calls_download_resource(monkeypatch):
    plan = {
        "downloads": [
            {"resource": "hf://models/org/one"},
            {"resource": "ms://models/org/two"},
        ]
    }
    calls = []

    def fake_download(resource, **kwargs):
        calls.append({"resource": resource, **kwargs})
        return f"/tmp/{resource.rsplit('/', 1)[-1]}"

    monkeypatch.setattr("modely.application.batch.download_resource", fake_download)

    result = run_batch_download(plan, local_dir="./models", profile="minimal", include=["*.json"], exclude=["*.bin"], prefer="hf,ms", fallback=True, retries=2, timeout=5, checksum=True, resume=False)

    assert result["ok"] is True
    assert [call["resource"] for call in calls] == ["hf://models/org/one", "ms://models/org/two"]
    assert calls[0]["local_dir"] == "./models"
    assert calls[0]["profile"] == "minimal"
    assert calls[0]["include"] == ["*.json"]
    assert calls[0]["exclude"] == ["*.bin"]
    assert calls[0]["fallback"] is True
    assert calls[0]["resume"] is False


def test_run_batch_download_reports_failures(monkeypatch):
    plan = {"downloads": [{"resource": "hf://models/good"}, {"resource": "hf://models/bad"}]}

    def fake_download(resource, **kwargs):
        if resource.endswith("bad"):
            raise RuntimeError("boom")
        return "/tmp/good"

    monkeypatch.setattr("modely.application.batch.download_resource", fake_download)

    result = run_batch_download(plan)

    assert result["ok"] is False
    assert result["summary"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert result["results"][1]["error"] == "boom"


def test_batch_download_plan_json_serializable(monkeypatch):
    monkeypatch.setattr("modely.application.batch.search", lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])] )

    plan = create_batch_download_plan(None, tags=["tag"])

    assert json.loads(json.dumps(plan))["downloads"][0]["resource"] == "hf://models/org/model"


def test_print_batch_download_dry_run_is_readable(capsys):
    print_batch_download_result(
        {
            "dry_run": True,
            "keyword": "qwen",
            "source": "hf",
            "repo_type": "model",
            "tags": ["text-generation"],
            "matched_count": 2,
            "selected_count": 1,
            "downloads": [{"resource": "hf://models/org/model", "tags": ["text-generation", "transformers"]}],
        }
    )

    output = capsys.readouterr().out
    assert "Batch download preview" in output
    assert "Filters:" in output
    assert "Matched:  2" in output
    assert "1. hf://models/org/model" in output
    assert "Add --yes" in output


def test_batch_download_cli_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download", "qwen", "--tag", "tag", "--json"])
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])],
    )

    modely.main()

    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True
    assert output["downloads"][0]["resource"] == "hf://models/org/model"


def test_batch_download_cli_accepts_task_without_tag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download", "--task", "text-generation", "--repo-type", "model", "--json"])
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=[])],
    )

    modely.main()

    output = json.loads(capsys.readouterr().out)
    assert output["downloads"][0]["resource"] == "hf://models/org/model"


def test_batch_download_cli_yes_exits_nonzero_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download", "qwen", "--tag", "tag", "--yes"])
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])],
    )
    monkeypatch.setattr("modely.application.batch.download_resource", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(SystemExit) as exc:
        modely.main()

    assert exc.value.code == 1
    assert "Failures:" in capsys.readouterr().out


def test_create_batch_download_plan_forwards_all_search_filters(monkeypatch):
    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return [SearchResult(id="org/model", source="hf", repo_type="model", tags=[])]

    monkeypatch.setattr("modely.application.batch.search", fake_search)

    create_batch_download_plan(
        "qwen",
        source="hf",
        repo_type="model",
        tags=[],
        limit=7,
        search_limit=11,
        task="text-generation",
        library="transformers",
        license="apache-2.0",
        sort="likes",
        direction="asc",
        author="org",
        after="2024-01-01",
        before="2024-12-31",
        full=True,
    )

    assert captured == {
        "keyword": "qwen",
        "source": "hf",
        "repo_type": "model",
        "task": "text-generation",
        "library": "transformers",
        "license": "apache-2.0",
        "sort": "likes",
        "direction": "asc",
        "limit": 11,
        "author": "org",
        "after": "2024-01-01",
        "before": "2024-12-31",
        "full": True,
    }


def test_create_batch_download_plan_normalizes_tags(monkeypatch):
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["A", "b"])],
    )

    plan = create_batch_download_plan(None, tags=[" B ", "a", "A", " "])

    assert plan["tags"] == ["a", "b"]
    assert plan["downloads"][0]["resource"] == "hf://models/org/model"


def test_create_batch_download_plan_rejects_non_positive_limits(monkeypatch):
    monkeypatch.setattr("modely.application.batch.search", lambda **kwargs: [])

    with pytest.raises(ValueError, match="limit must be positive"):
        create_batch_download_plan("qwen", tags=[], limit=0)
    with pytest.raises(ValueError, match="limit must be positive"):
        create_batch_download_plan("qwen", tags=[], limit=-1)
    with pytest.raises(ValueError, match="search_limit must be positive"):
        create_batch_download_plan("qwen", tags=[], search_limit=0)
    with pytest.raises(ValueError, match="search_limit must be positive"):
        create_batch_download_plan("qwen", tags=[], search_limit=-1)


def test_print_batch_download_dry_run_includes_structured_filters(capsys):
    print_batch_download_result(
        {
            "dry_run": True,
            "keyword": None,
            "source": "hf",
            "repo_type": "model",
            "tags": [],
            "task": "text-generation",
            "library": "transformers",
            "license": "apache-2.0",
            "author": "org",
            "after": "2024-01-01",
            "before": "2024-12-31",
            "matched_count": 1,
            "selected_count": 1,
            "downloads": [{"resource": "hf://models/org/model", "tags": []}],
        }
    )

    output = capsys.readouterr().out
    assert "task=text-generation" in output
    assert "library=transformers" in output
    assert "license=apache-2.0" in output
    assert "author=org" in output
    assert "after=2024-01-01" in output
    assert "before=2024-12-31" in output


def test_print_batch_download_dry_run_no_matches(capsys):
    print_batch_download_result(
        {
            "dry_run": True,
            "keyword": "qwen",
            "source": "hf",
            "repo_type": "model",
            "tags": ["missing"],
            "matched_count": 0,
            "selected_count": 0,
            "downloads": [],
        }
    )

    assert "No resources matched the requested filters." in capsys.readouterr().out


def test_run_batch_download_fail_fast_stops_after_first_failure(monkeypatch):
    plan = {
        "downloads": [
            {"resource": "hf://models/good"},
            {"resource": "hf://models/bad"},
            {"resource": "hf://models/skipped"},
        ]
    }
    calls = []

    def fake_download(resource, **kwargs):
        calls.append(resource)
        if resource.endswith("bad"):
            raise RuntimeError("boom")
        return "/tmp/good"

    monkeypatch.setattr("modely.application.batch.download_resource", fake_download)

    result = run_batch_download(plan, fail_fast=True)

    assert calls == ["hf://models/good", "hf://models/bad"]
    assert result["summary"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert result["ok"] is False


def test_run_batch_download_forwards_all_download_options(monkeypatch):
    captured = {}

    def fake_download(resource, **kwargs):
        captured.update(kwargs)
        return "/tmp/model"

    monkeypatch.setattr("modely.application.batch.download_resource", fake_download)

    result = run_batch_download(
        {"downloads": [{"resource": "hf://models/org/model"}]},
        local_dir="./models",
        cache_dir="./cache",
        token="secret",
        include=["*.json"],
        exclude=["*.bin"],
        profile="minimal",
        prefer="hf,ms",
        fallback=True,
        force_download=True,
        backend="official",
        with_lfs=True,
        endpoint="https://example.test",
        max_workers=4,
        timeout=5,
        retries=2,
        checksum=True,
        resume=False,
    )

    assert result["ok"] is True
    assert captured == {
        "cache_dir": "./cache",
        "local_dir": "./models",
        "token": "secret",
        "include": ["*.json"],
        "exclude": ["*.bin"],
        "prefer": "hf,ms",
        "fallback": True,
        "force_download": True,
        "backend": "official",
        "with_lfs": True,
        "profile": "minimal",
        "endpoint": "https://example.test",
        "max_workers": 4,
        "timeout": 5,
        "retries": 2,
        "checksum": True,
        "resume": False,
    }


def test_batch_download_cli_rejects_empty_filters(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download"])

    with pytest.raises(SystemExit) as exc:
        modely.main()

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "Missing search filter" in output
    assert "--tag TAG" in output
    assert "--task TASK" in output
    assert "Example:" in output


def test_batch_download_cli_yes_json_success(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["modely", "batch-download", "qwen", "--tag", "tag", "--yes", "--json"])
    monkeypatch.setattr(
        "modely.application.batch.search",
        lambda **kwargs: [SearchResult(id="org/model", source="hf", repo_type="model", tags=["tag"])],
    )
    monkeypatch.setattr("modely.application.batch.download_resource", lambda *a, **k: "/tmp/model")

    modely.main()

    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is False
    assert output["ok"] is True
    assert output["summary"]["succeeded"] == 1
    assert output["results"][0]["path"] == "/tmp/model"
