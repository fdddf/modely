"""Unit and integration tests for the search module."""

import json
import types
from datetime import datetime, timezone

import pytest

import modely  # noqa: ensure package is imported before submodule access
import modely.search.hf_search as hf_mod
import modely.search.ms_search as ms_mod
import modely.search as search_mod
import modely.search.gh_search as gh_mod
from modely.search import SearchResult, search, main as search_main
from modely.search.display import format_table, format_json, _format_count, _format_date


# ── Helpers ─────────────────────────────────────────────────────

def _mock_model_info(**overrides):
    """Create a fake ModelInfo / DatasetInfo object via SimpleNamespace."""
    defaults = {
        "id": "test-org/test-model",
        "author": "test-org",
        "downloads": 1_000_000,
        "likes": 500,
        "last_modified": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "created_at": datetime(2023, 1, 15, tzinfo=timezone.utc),
        "pipeline_tag": "text-classification",
        "library_name": "transformers",
        "tags": ["pytorch", "bert"],
        "license": "mit",
        "description": "A test model",
    }
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


# ── SearchResult dataclass ──────────────────────────────────────

class TestSearchResult:
    def test_defaults(self):
        r = SearchResult(id="a/b", source="hf", repo_type="model")
        assert r.downloads == 0
        assert r.likes == 0
        assert r.tags == []

    def test_full_fields(self):
        r = SearchResult(
            id="a/b",
            source="hf",
            repo_type="model",
            author="author1",
            downloads=100,
            likes=10,
            last_modified="2024-01-01",
            created_at="2023-01-01",
            pipeline_tag="text-generation",
            library_name="transformers",
            tags=["tag1"],
            license="mit",
            description="desc",
        )
        assert r.author == "author1"
        assert r.downloads == 100


# ── Display ─────────────────────────────────────────────────────

class TestFormatCount:
    def test_millions(self):
        assert _format_count(5_200_000) == "5.2M"

    def test_thousands(self):
        assert _format_count(1_500) == "1.5K"

    def test_small(self):
        assert _format_count(42) == "42"

    def test_zero(self):
        assert _format_count(0) == "0"


class TestFormatDate:
    def test_iso(self):
        assert _format_date("2024-06-01T12:00:00+00:00") == "2024-06-01"

    def test_none(self):
        assert _format_date(None) == "-"

    def test_short(self):
        assert _format_date("2024-06-01") == "2024-06-01"


class TestFormatTable:
    def test_empty(self):
        assert format_table([]) == "No results found."

    def test_single_result(self):
        r = SearchResult(id="org/model", source="hf", repo_type="model",
                         pipeline_tag="text-gen", downloads=1000, likes=50,
                         last_modified="2024-06-01")
        output = format_table([r])
        assert "org/model" in output
        assert "HF" in output
        assert "text-gen" in output
        assert "1.0K" in output

    def test_result_count_shown(self):
        r = SearchResult(id="a/b", source="hf", repo_type="model")
        output = format_table([r])
        assert "1 result(s) shown" in output

    def test_long_id_truncated(self):
        r = SearchResult(id="x" * 60, source="hf", repo_type="model")
        output = format_table([r])
        assert "..." in output


class TestFormatJson:
    def test_valid_json(self):
        r = SearchResult(id="a/b", source="hf", repo_type="model")
        j = format_json([r])
        parsed = json.loads(j)
        assert parsed[0]["id"] == "a/b"
        assert parsed[0]["source"] == "hf"

    def test_empty(self):
        assert format_json([]) == "[]"


# ── HF Search (unit) ────────────────────────────────────────────

class TestHuggingFaceSearch:
    def test_returns_list_of_search_results(self, monkeypatch):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test", repo_type="model")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].id == "test-org/test-model"
        assert results[0].source == "hf"

    def test_dataset_repo_type(self, monkeypatch):
        fake_info = _mock_model_info(id="org/dataset", pipeline_tag=None)

        def mock_list_datasets(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_datasets", mock_list_datasets)

        results = hf_mod.search_huggingface("test", repo_type="dataset")
        assert len(results) == 1
        assert results[0].id == "org/dataset"

    def test_empty_results(self, monkeypatch):
        def mock_list_models(self, **kwargs):
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("no-match")
        assert results == []

    def test_error_handled_gracefully(self, monkeypatch):
        def mock_list_models(self, **kwargs):
            raise RuntimeError("API down")

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test")
        assert results == []

    def test_maps_datetime_fields(self, monkeypatch):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        fake_info = _mock_model_info(last_modified=dt, created_at=dt)

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test")
        assert results[0].last_modified == "2025-01-15T12:00:00+00:00"
        assert results[0].created_at == "2025-01-15T12:00:00+00:00"

    def test_maps_tags_list(self, monkeypatch):
        fake_info = _mock_model_info(tags=["tag-a", "tag-b"])

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test")
        assert "tag-a" in results[0].tags
        assert "tag-b" in results[0].tags

    def test_task_filter_passed_to_api(self, monkeypatch):
        """Verify the task parameter is passed as a filter to the HF API."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", task="text-classification")
        assert "filter" in captured
        assert "text-classification" in captured["filter"]

    def test_library_filter_passed_to_api(self, monkeypatch):
        """Verify the library parameter is passed as a filter."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", library="transformers")
        assert "transformers" in captured["filter"]

    def test_license_filter_passed_to_api(self, monkeypatch):
        """Verify the license parameter is passed as 'license:<name>'."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", license="mit")
        assert "license:mit" in captured["filter"]

    def test_author_passed_to_api(self, monkeypatch):
        """Verify the author parameter is passed directly."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", author="test-org")
        assert captured["author"] == "test-org"

    def test_full_flag_passed_to_api(self, monkeypatch):
        """Verify the full=True parameter is passed to the API."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", full=True)
        assert captured["full"] is True

    def test_full_flag_false_by_default(self, monkeypatch):
        """Verify full=False by default (not full=True)."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test")
        assert captured.get("full") is False or captured.get("full") is None

    def test_limit_passed_to_api(self, monkeypatch):
        """Verify the limit parameter is passed to the API."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", limit=5)
        assert captured["limit"] == 5

    def test_search_keyword_passed_to_api(self, monkeypatch):
        """Verify the keyword is passed as the search parameter."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("gpt2")
        assert captured["search"] == "gpt2"

    def test_sort_passed_to_api(self, monkeypatch):
        """Verify sort fields are mapped correctly."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", sort="lastModified")
        assert captured["sort"] == "last_modified"

    def test_sort_downloads_mapped(self, monkeypatch):
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", sort="downloads")
        assert captured["sort"] == "downloads"

    def test_sort_likes_mapped(self, monkeypatch):
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", sort="likes")
        assert captured["sort"] == "likes"

    def test_sort_created_at_mapped(self, monkeypatch):
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", sort="created_at")
        assert captured["sort"] == "created_at"

    def test_asc_direction_reverses_results(self, monkeypatch):
        """Ascending direction should reverse the API results."""
        low = _mock_model_info(id="low", downloads=100)
        high = _mock_model_info(id="high", downloads=10000)

        def mock_list_models(self, **kwargs):
            return [high, low]  # API returns desc by default

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = hf_mod.search_huggingface("test", direction="asc")
        assert results[0].id == "low"
        assert results[1].id == "high"

    def test_dataset_with_task(self, monkeypatch):
        """Task filter should work with datasets too."""
        captured = {}

        def mock_list_datasets(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_datasets", mock_list_datasets)
        hf_mod.search_huggingface("test", repo_type="dataset", task="nlp")
        assert "filter" in captured
        assert "nlp" in captured["filter"]

    def test_no_filters_when_all_none(self, monkeypatch):
        """When no optional filters are set, the filter arg should be None."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test")
        assert captured["filter"] is None

    def test_multiple_filters_combined(self, monkeypatch):
        """Task + library + license should all be in the filter list."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        hf_mod.search_huggingface("test", task="text-gen", library="pytorch", license="apache-2.0")
        filters = captured["filter"]
        assert "text-gen" in filters
        assert "pytorch" in filters
        assert "license:apache-2.0" in filters

    def test_tags_none_handled(self, monkeypatch):
        """When tags is None, it should not crash."""
        fake_info = _mock_model_info(tags=None)

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        results = hf_mod.search_huggingface("test")
        assert results[0].tags == []

    def test_none_downloads_defaults_to_zero(self, monkeypatch):
        """When downloads is None, it should default to 0."""
        fake_info = _mock_model_info(downloads=None)

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        results = hf_mod.search_huggingface("test")
        assert results[0].downloads == 0

    def test_none_likes_defaults_to_zero(self, monkeypatch):
        """When likes is None, it should default to 0."""
        fake_info = _mock_model_info(likes=None)

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        results = hf_mod.search_huggingface("test")
        assert results[0].likes == 0

    def test_last_modified_without_isoformat(self, monkeypatch):
        """String last_modified should be preserved directly."""
        fake_info = _mock_model_info(last_modified="2024-06-01T00:00:00Z")

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        results = hf_mod.search_huggingface("test")
        # SimpleNamespace stores the string directly, no isoformat method
        # The code checks hasattr for isoformat; if absent, uses the value as-is
        assert results[0].last_modified is not None

    def test_hf_url_is_correct(self, monkeypatch):
        """The URL field should point to huggingface.co."""
        fake_info = _mock_model_info(id="org/model-name")

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        results = hf_mod.search_huggingface("test")
        assert results[0].url == "https://huggingface.co/org/model-name"


# ── MS Search (unit) ────────────────────────────────────────────

class TestModelScopeSearch:
    def test_returns_list_of_search_results(self, monkeypatch):
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "owner",
                                    "Name": "test-model",
                                    "Organization": "owner",
                                    "Downloads": 500,
                                    "Stars": 10,
                                    "CreatedTime": 1700000000,
                                    "LastUpdatedTime": 1717200000,
                                    "Tasks": [{"Name": "text-generation"}],
                                    "Tags": [{"Name": "nlp"}],
                                    "License": "mit",
                                    "Description": "A test model",
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }

            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", repo_type="model")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].id == "owner/test-model"
        assert results[0].source == "ms"
        assert results[0].pipeline_tag == "text-generation"

    def test_dataset_search_returns_results(self, monkeypatch):
        """Dataset search should use OpenAPI v1 endpoint and return proper results."""
        class FakeResponse:
            def json(self):
                return {
                    "success": True,
                    "data": {
                        "datasets": [
                            {
                                "id": "owner/test-dataset",
                                "display_name": "test-dataset",
                                "description": "A test dataset",
                                "downloads": 100,
                                "likes": 5,
                                "tasks": ["text-classification"],
                                "tags": ["nlp"],
                                "license": "mit",
                                "created_at": "2024-01-15T00:00:00Z",
                                "last_modified": "2024-06-01T12:00:00Z",
                            }
                        ],
                        "total_count": 1,
                    },
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "get",
            lambda url, params, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", repo_type="dataset")
        assert len(results) == 1
        assert results[0].repo_type == "dataset"
        assert results[0].id == "owner/test-dataset"
        assert "datasets" in results[0].url

    def test_timeout_handled(self, monkeypatch):
        def mock_put(**kwargs):
            raise ms_mod.requests.exceptions.Timeout()

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_connection_error_handled(self, monkeypatch):
        def mock_put(**kwargs):
            raise ms_mod.requests.exceptions.ConnectionError()

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_empty_response(self, monkeypatch):
        class FakeResponse:
            def json(self):
                return {}

            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_task_filter_in_request_body(self, monkeypatch):
        """Task parameter should be included in the JSON body."""
        captured = {}

        def mock_put(url, json, timeout, headers):
            captured["body"] = json
            resp = ms_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {"Data": {"Model": {"Models": [], "TotalCount": 0}}}
            return resp

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)
        ms_mod.search_modelscope("test", task="text-generation")
        assert captured["body"]["tasks"] == ["text-generation"]

    def test_no_task_means_empty_tasks_list(self, monkeypatch):
        """When no task is given, the tasks field should be an empty list."""
        captured = {}

        def mock_put(url, json, timeout, headers):
            captured["body"] = json
            resp = ms_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {"Data": {"Model": {"Models": [], "TotalCount": 0}}}
            return resp

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)
        ms_mod.search_modelscope("test")
        assert captured["body"]["tasks"] == []

    def test_sort_by_downloads_default(self, monkeypatch):
        """Default sort should be by downloads descending."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "low", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []},
                                {"Path": "a", "Name": "high", "Downloads": 10000, "Stars": 5, "Tasks": [], "Tags": []},
                            ],
                            "TotalCount": 2,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results[0].id == "a/high"
        assert results[1].id == "a/low"

    def test_sort_by_likes(self, monkeypatch):
        """Sort by likes should order by likes field."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "low", "Downloads": 1000, "Stars": 100, "Likes": 1, "Tasks": [], "Tags": []},
                                {"Path": "a", "Name": "high", "Downloads": 100, "Stars": 0, "Likes": 500, "Tasks": [], "Tags": []},
                            ],
                            "TotalCount": 2,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", sort="likes")
        assert results[0].id == "a/high"  # 500 likes
        assert results[1].id == "a/low"   # 1 like

    def test_sort_by_last_modified(self, monkeypatch):
        """Sort by lastModified should order by LastUpdatedTime."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "older", "Downloads": 100, "Stars": 5,
                                 "CreatedTime": 1700000000, "LastUpdatedTime": 1700000000, "Tasks": [], "Tags": []},
                                {"Path": "a", "Name": "newer", "Downloads": 100, "Stars": 5,
                                 "CreatedTime": 1700000000, "LastUpdatedTime": 1720000000, "Tasks": [], "Tags": []},
                            ],
                            "TotalCount": 2,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", sort="lastModified")
        assert results[0].id == "a/newer"
        assert results[1].id == "a/older"

    def test_sort_by_created_at(self, monkeypatch):
        """Sort by created_at should order by CreatedTime."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "older", "Downloads": 100, "Stars": 5,
                                 "CreatedTime": 1500000000, "LastUpdatedTime": 1700000000, "Tasks": [], "Tags": []},
                                {"Path": "a", "Name": "newer", "Downloads": 100, "Stars": 5,
                                 "CreatedTime": 1600000000, "LastUpdatedTime": 1700000000, "Tasks": [], "Tags": []},
                            ],
                            "TotalCount": 2,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", sort="created_at")
        assert results[0].id == "a/newer"
        assert results[1].id == "a/older"

    def test_sort_asc_direction(self, monkeypatch):
        """Ascending direction should reverse sort order."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "high", "Downloads": 10000, "Stars": 5, "Tasks": [], "Tags": []},
                                {"Path": "a", "Name": "low", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []},
                            ],
                            "TotalCount": 2,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test", direction="asc")
        assert results[0].id == "a/low"
        assert results[1].id == "a/high"

    def test_limit_in_request_body(self, monkeypatch):
        """Limit should be passed as PageSize in the JSON body."""
        captured = {}

        def mock_put(url, json, timeout, headers):
            captured["body"] = json
            resp = ms_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {"Data": {"Model": {"Models": [], "TotalCount": 0}}}
            return resp

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)
        ms_mod.search_modelscope("test", limit=5)
        assert captured["body"]["PageSize"] == 5

    def test_pagenumber_in_request_body(self, monkeypatch):
        """PageNumber should be 1 by default."""
        captured = {}

        def mock_put(url, json, timeout, headers):
            captured["body"] = json
            resp = ms_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {"Data": {"Model": {"Models": [], "TotalCount": 0}}}
            return resp

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)
        ms_mod.search_modelscope("test")
        assert captured["body"]["PageNumber"] == 1

    def test_keyword_in_request_body(self, monkeypatch):
        """Keyword should be in the Name field of the JSON body."""
        captured = {}

        def mock_put(url, json, timeout, headers):
            captured["body"] = json
            resp = ms_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {"Data": {"Model": {"Models": [], "TotalCount": 0}}}
            return resp

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)
        ms_mod.search_modelscope("qwen")
        assert captured["body"]["Name"] == "qwen"

    def test_tags_is_list_of_dicts(self, monkeypatch):
        """When Tags is a list of dicts, extract 'Name' or 'value'."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "a",
                                    "Name": "b",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "Tags": [{"Name": "nlp"}, {"Name": "chat"}],
                                    "Tasks": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert "nlp" in results[0].tags
        assert "chat" in results[0].tags

    def test_tasks_is_list_of_strings(self, monkeypatch):
        """When Tasks is a list of strings (not dicts), use first string."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "a",
                                    "Name": "b",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "Tasks": ["text-generation"],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results[0].pipeline_tag == "text-generation"

    def test_none_likes_falls_back_to_stars(self, monkeypatch):
        """When Likes is None, fall back to Stars."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "a",
                                    "Name": "b",
                                    "Downloads": 100,
                                    "Stars": 42,
                                    "Likes": None,
                                    "Tasks": [],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results[0].likes == 42

    def test_only_name_no_path(self, monkeypatch):
        """When Path is missing, use Name as the ID."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Name": "standalone-model",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "Tasks": [],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results[0].id == "standalone-model"

    def test_http_error_handled(self, monkeypatch):
        """HTTPError should be caught and return empty list."""
        def mock_put(**kwargs):
            resp = ms_mod.requests.Response()
            resp.status_code = 500
            resp.raise_for_status = lambda: (_ for _ in ()).throw(ms_mod.requests.exceptions.HTTPError("500"))
            return resp

        monkeypatch.setattr(ms_mod.requests, "put", mock_put)

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_invalid_json_handled(self, monkeypatch):
        """Invalid JSON response should be caught."""

        class FakeResponse:
            def json(self):
                raise ms_mod.json.JSONDecodeError("bad json", "", 0)
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results == []

    def test_url_contains_modelscope_cn(self, monkeypatch):
        """Generated URL should point to modelscope.cn."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "owner", "Name": "model", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []}
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert "modelscope.cn/models/" in results[0].url

    def test_organization_as_author(self, monkeypatch):
        """Organization field should be used as author."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "org",
                                    "Name": "model",
                                    "Organization": "MyOrg",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "Tasks": [],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results[0].author == "MyOrg"

    def test_description_falls_back_to_chinese_name(self, monkeypatch):
        """When Description is missing, fall back to ChineseName."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "a",
                                    "Name": "b",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "ChineseName": "中文名称",
                                    "Tasks": [],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert results[0].description == "中文名称"

    def test_malformed_item_skipped(self, monkeypatch):
        """A malformed item that throws during parsing should be skipped."""
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                None,  # would crash .get() on None
                                {"Path": "a", "Name": "good", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []},
                            ],
                            "TotalCount": 2,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = ms_mod.search_modelscope("test")
        assert len(results) == 1
        assert results[0].id == "a/good"


# ── Orchestrator ────────────────────────────────────────────────

class TestSearchOrchestrator:
    def test_source_hf_only(self, monkeypatch):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("gpt2", source="hf")
        assert len(results) == 1
        assert results[0].source == "hf"

    def test_source_ms_only(self, monkeypatch):
        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {
                                    "Path": "a",
                                    "Name": "b",
                                    "Downloads": 100,
                                    "Stars": 5,
                                    "Tasks": [],
                                    "Tags": [],
                                }
                            ],
                            "TotalCount": 1,
                        }
                    }
                }

            def raise_for_status(self):
                pass

        monkeypatch.setattr(ms_mod.requests, "put",
            lambda url, json, timeout, headers: FakeResponse())

        results = search("gpt2", source="ms")
        assert len(results) == 1
        assert results[0].source == "ms"

    def test_date_filter_applied(self, monkeypatch):
        old = _mock_model_info(id="old-model", last_modified=datetime(2022, 1, 1, tzinfo=timezone.utc))
        new = _mock_model_info(id="new-model", last_modified=datetime(2024, 6, 1, tzinfo=timezone.utc))

        def mock_list_models(self, **kwargs):
            return [old, new]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", after="2023-01-01")
        ids = [r.id for r in results]
        assert "new-model" in ids
        assert "old-model" not in ids

    def test_sort_desc_downloads(self, monkeypatch):
        low = _mock_model_info(id="low", downloads=100)
        high = _mock_model_info(id="high", downloads=10000)

        def mock_list_models(self, **kwargs):
            return [low, high]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", sort="downloads", direction="desc")
        assert results[0].id == "high"
        assert results[1].id == "low"

    def test_unknown_source_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            search("test", source="bad")

    def test_before_date_filter(self, monkeypatch):
        """Results after the 'before' date should be excluded."""
        old = _mock_model_info(id="old-model", last_modified=datetime(2022, 1, 1, tzinfo=timezone.utc))
        new = _mock_model_info(id="new-model", last_modified=datetime(2024, 6, 1, tzinfo=timezone.utc))

        def mock_list_models(self, **kwargs):
            return [old, new]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", before="2023-01-01")
        ids = [r.id for r in results]
        assert "old-model" in ids
        assert "new-model" not in ids

    def test_both_after_and_before_filter(self, monkeypatch):
        """Both after and before filters should work together."""
        very_old = _mock_model_info(id="very-old", last_modified=datetime(2021, 1, 1, tzinfo=timezone.utc))
        mid = _mock_model_info(id="mid", last_modified=datetime(2023, 6, 1, tzinfo=timezone.utc))
        very_new = _mock_model_info(id="very-new", last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc))

        def mock_list_models(self, **kwargs):
            return [very_old, mid, very_new]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", after="2022-01-01", before="2024-01-01")
        ids = [r.id for r in results]
        assert "mid" in ids
        assert "very-old" not in ids
        assert "very-new" not in ids

    def test_result_without_date_passed_through(self, monkeypatch):
        """Results with no last_modified date should pass through date filter."""
        no_date = _mock_model_info(id="no-date", last_modified=None)

        def mock_list_models(self, **kwargs):
            return [no_date]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", after="2024-01-01")
        assert len(results) == 1
        assert results[0].id == "no-date"

    def test_sort_by_likes(self, monkeypatch):
        low_likes = _mock_model_info(id="low", downloads=1000, likes=10)
        high_likes = _mock_model_info(id="high", downloads=10, likes=5000)

        def mock_list_models(self, **kwargs):
            return [low_likes, high_likes]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", sort="likes", direction="desc")
        assert results[0].id == "high"
        assert results[1].id == "low"

    def test_sort_by_last_modified(self, monkeypatch):
        older = _mock_model_info(id="older", last_modified=datetime(2023, 1, 1, tzinfo=timezone.utc))
        newer = _mock_model_info(id="newer", last_modified=datetime(2024, 6, 1, tzinfo=timezone.utc))

        def mock_list_models(self, **kwargs):
            return [older, newer]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", sort="lastModified", direction="desc")
        assert results[0].id == "newer"
        assert results[1].id == "older"

    def test_sort_by_created_at(self, monkeypatch):
        older = _mock_model_info(id="older", created_at=datetime(2022, 1, 1, tzinfo=timezone.utc))
        newer = _mock_model_info(id="newer", created_at=datetime(2023, 6, 1, tzinfo=timezone.utc))

        def mock_list_models(self, **kwargs):
            return [older, newer]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", sort="created_at", direction="desc")
        assert results[0].id == "newer"
        assert results[1].id == "older"

    def test_sort_asc_direction(self, monkeypatch):
        low = _mock_model_info(id="low", downloads=100)
        high = _mock_model_info(id="high", downloads=10000)

        def mock_list_models(self, **kwargs):
            return [high, low]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf", sort="downloads", direction="asc")
        assert results[0].id == "low"
        assert results[1].id == "high"

    def test_task_passed_to_orchestrator(self, monkeypatch):
        """Task parameter should be forwarded to HF backend."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        search("test", source="hf", task="text-classification")
        assert "filter" in captured
        assert "text-classification" in captured["filter"]

    def test_library_passed_to_orchestrator(self, monkeypatch):
        """Library parameter should be forwarded to HF backend."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        search("test", source="hf", library="transformers")
        assert "transformers" in captured["filter"]

    def test_author_passed_to_orchestrator(self, monkeypatch):
        """Author parameter should be forwarded to HF backend."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        search("test", source="hf", author="test-org")
        assert captured["author"] == "test-org"

    def test_source_all_parallel_fetch(self, monkeypatch):
        """When source='all', HF, MS and GitHub backends should be called."""
        hf_called = []
        ms_called = []
        gh_called = []

        def mock_list_models(self, **kwargs):
            hf_called.append(True)
            return [_mock_model_info(id="hf-model")]

        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "b", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []}
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        monkeypatch.setattr(ms_mod.requests, "put", lambda url, json, timeout, headers: FakeResponse())
        # Mock GitHub search to return empty (unit test, no network)
        monkeypatch.setattr(search_mod, "search_github", lambda **kwargs: [])

        results = search("test", source="all")
        assert len(hf_called) > 0
        assert len(results) >= 1
        sources = {r.source for r in results}
        assert "hf" in sources
        assert "ms" in sources

    def test_source_all_hf_error_does_not_block_ms(self, monkeypatch):
        """When HF backend fails, MS results should still be returned."""
        def mock_list_models(self, **kwargs):
            raise RuntimeError("HF down")

        class FakeResponse:
            def json(self):
                return {
                    "Data": {
                        "Model": {
                            "Models": [
                                {"Path": "a", "Name": "b", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []}
                            ],
                            "TotalCount": 1,
                        }
                    }
                }
            def raise_for_status(self):
                pass

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        monkeypatch.setattr(ms_mod.requests, "put", lambda url, json, timeout, headers: FakeResponse())
        # Mock GitHub search to return empty
        monkeypatch.setattr(search_mod, "search_github", lambda **kwargs: [])

        results = search("test", source="all")
        assert len(results) >= 1
        assert all(r.source == "ms" for r in results)

    def test_full_flag_passed_through(self, monkeypatch):
        """The full flag should be forwarded to HF backend."""
        captured = {}

        def mock_list_models(self, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        search("test", source="hf", full=True)
        assert captured["full"] is True

    def test_repo_type_passed_through(self, monkeypatch):
        """repo_type should be forwarded; datasets uses list_datasets."""
        captured = {}

        def mock_list_datasets(self, **kwargs):
            captured.update(kwargs)
            return [_mock_model_info(id="org/dataset")]

        monkeypatch.setattr(hf_mod.HfApi, "list_datasets", mock_list_datasets)
        results = search("test", source="hf", repo_type="dataset")
        assert len(results) == 1
        assert results[0].id == "org/dataset"

    def test_default_sort_is_downloads(self, monkeypatch):
        """When no sort specified, default to downloads descending."""
        low = _mock_model_info(id="low", downloads=100)
        high = _mock_model_info(id="high", downloads=10000)

        def mock_list_models(self, **kwargs):
            return [low, high]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        results = search("test", source="hf")
        assert results[0].id == "high"
        assert results[1].id == "low"


# ── CLI main ────────────────────────────────────────────────────

class TestSearchMain:
    def test_outputs_table_by_default(self, monkeypatch, capsys):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        args = types.SimpleNamespace(
            keyword="test",
            source="hf",
            repo_type="model",
            task=None,
            library=None,
            license=None,
            sort="downloads",
            direction="desc",
            limit=20,
            author=None,
            after=None,
            before=None,
            full=False,
            json=False,
        )
        search_main(args)
        out = capsys.readouterr().out
        assert "test-org/test-model" in out
        assert "1 result(s) shown" in out

    def test_json_output(self, monkeypatch, capsys):
        fake_info = _mock_model_info()

        def mock_list_models(self, **kwargs):
            return [fake_info]

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        args = types.SimpleNamespace(
            keyword="test",
            source="hf",
            repo_type="model",
            task=None,
            library=None,
            license=None,
            sort="downloads",
            direction="desc",
            limit=20,
            author=None,
            after=None,
            before=None,
            full=False,
            json=True,
        )
        search_main(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed[0]["id"] == "test-org/test-model"

    def test_backend_error_shows_empty_results(self, monkeypatch, capsys):
        """When the backend raises, search_main gracefully shows no results."""
        def mock_list_models(self, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)

        args = types.SimpleNamespace(
            keyword="test",
            source="hf",
            repo_type="model",
            task=None,
            library=None,
            license=None,
            sort="downloads",
            direction="desc",
            limit=20,
            author=None,
            after=None,
            before=None,
            full=False,
            json=False,
        )
        search_main(args)
        out = capsys.readouterr().out
        # Should gracefully show no results, not crash
        assert "No results found" in out


# ── CLI Integration (subprocess) ────────────────────────────────

@pytest.mark.integration
class TestSearchIntegration:
    def test_hf_search_returns_results(self):
        """Real search against Hugging Face should return at least one result."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "gpt2", "--source", "hf", "--limit", "3"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "gpt2" in result.stdout.lower() or "result" in result.stdout.lower()

    def test_json_output_valid(self):
        """JSON output should be parseable and non-empty."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "gpt2", "--source", "hf", "--limit", "2", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)
        assert len(parsed) > 0
        assert "id" in parsed[0]

    def test_dataset_search(self):
        """Search for datasets."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "glue", "--source", "hf", "--repo-type", "dataset", "--limit", "3", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, list)

    def test_ms_search_returns_results(self):
        """Real search against ModelScope should not crash."""
        import subprocess
        result = subprocess.run(
            ["modely-ai", "search", "qwen", "--source", "ms", "--limit", "3", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        json.loads(result.stdout)


# ── GitHub Search (unit) ─────────────────────────────────────────

class TestGitHubSearch:
    def test_returns_list_of_search_results(self, monkeypatch):
        fake_response = {
            "items": [
                {
                    "full_name": "huggingface/transformers",
                    "html_url": "https://github.com/huggingface/transformers",
                    "description": "Transformers framework",
                    "stargazers_count": 150000,
                    "forks_count": 25000,
                    "language": "Python",
                    "topics": ["nlp", "pytorch"],
                    "license": {"spdx_id": "Apache-2.0"},
                    "owner": {"login": "huggingface"},
                    "created_at": "2018-10-29T13:56:00Z",
                    "updated_at": "2024-06-01T12:00:00Z",
                }
            ]
        }

        def mock_get(url, params, headers, timeout):
            resp = gh_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: fake_response
            return resp

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)

        results = gh_mod.search_github("transformers")
        assert len(results) == 1
        r = results[0]
        assert r.id == "huggingface/transformers"
        assert r.source == "github"
        assert r.likes == 150000
        assert r.downloads == 25000
        assert r.pipeline_tag == "Python"
        assert "Apache-2.0" in r.license
        assert "nlp" in r.tags

    def test_empty_results(self, monkeypatch):
        def mock_get(url, params, headers, timeout):
            resp = gh_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {"items": []}
            return resp

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)
        results = gh_mod.search_github("xyznonexistent")
        assert results == []

    def test_error_handled_gracefully(self, monkeypatch):
        def mock_get(url, params, headers, timeout):
            raise gh_mod.requests.exceptions.ConnectionError()

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)
        results = gh_mod.search_github("test")
        assert results == []

    def test_timeout_handled(self, monkeypatch):
        def mock_get(url, params, headers, timeout):
            raise gh_mod.requests.exceptions.Timeout()

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)
        results = gh_mod.search_github("test")
        assert results == []

    def test_maps_stars_to_likes(self, monkeypatch):
        fake_response = {
            "items": [{
                "full_name": "user/repo",
                "html_url": "https://github.com/user/repo",
                "stargazers_count": 42,
                "forks_count": 10,
                "language": None,
                "topics": [],
                "license": None,
                "owner": {"login": "user"},
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            }]
        }
        def mock_get(url, params, headers, timeout):
            resp = gh_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: fake_response
            return resp

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)
        results = gh_mod.search_github("test")
        assert results[0].likes == 42
        assert results[0].downloads == 10

    def test_maps_language_to_pipeline_tag(self, monkeypatch):
        fake_response = {
            "items": [{
                "full_name": "user/repo",
                "html_url": "https://github.com/user/repo",
                "stargazers_count": 1,
                "forks_count": 1,
                "language": "Rust",
                "topics": [],
                "license": None,
                "owner": {"login": "user"},
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            }]
        }
        def mock_get(url, params, headers, timeout):
            resp = gh_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: fake_response
            return resp

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)
        results = gh_mod.search_github("test")
        assert results[0].pipeline_tag == "Rust"

    def test_source_github_single(self, monkeypatch):
        """search(source='github') should return only GitHub results."""
        def mock_get(url, params, headers, timeout):
            resp = gh_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {
                "items": [{
                    "full_name": "user/repo", "html_url": "https://github.com/user/repo",
                    "stargazers_count": 10, "forks_count": 5, "language": "Go",
                    "topics": [], "license": None, "owner": {"login": "user"},
                    "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
                }]
            }
            return resp

        monkeypatch.setattr(gh_mod.requests, "get", mock_get)
        results = search("test", source="github")
        assert len(results) >= 1
        assert all(r.source == "github" for r in results)

    def test_gh_search_included_in_all(self, monkeypatch):
        """source='all' should include GitHub results alongside HF and MS."""
        # HF mock
        def mock_list_models(self, **kwargs):
            return [_mock_model_info(id="hf-model")]

        # MS mock
        class FakeMSResponse:
            def json(self):
                return {"Data": {"Model": {"Models": [
                    {"Path": "a", "Name": "b", "Downloads": 100, "Stars": 5, "Tasks": [], "Tags": []}
                ], "TotalCount": 1}}}
            def raise_for_status(self):
                pass

        # GH mock
        def mock_get(url, params, headers, timeout):
            resp = gh_mod.requests.Response()
            resp.status_code = 200
            resp.json = lambda: {
                "items": [{
                    "full_name": "gh/repo", "html_url": "https://github.com/gh/repo",
                    "stargazers_count": 1, "forks_count": 1, "language": "Python",
                    "topics": [], "license": None, "owner": {"login": "gh"},
                    "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-01T00:00:00Z",
                }]
            }
            return resp

        monkeypatch.setattr(hf_mod.HfApi, "list_models", mock_list_models)
        monkeypatch.setattr(ms_mod.requests, "put", lambda url, json, timeout, headers: FakeMSResponse())
        monkeypatch.setattr(gh_mod.requests, "get", mock_get)

        results = search("test", source="all")
        sources = {r.source for r in results}
        assert "hf" in sources
        assert "ms" in sources
        assert "github" in sources
