"""Unit tests for source profiles and probes."""

from modely.sources import list_source_profiles, rank_sources


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_list_source_profiles_contains_builtins():
    names = {p.name for p in list_source_profiles()}
    assert {"hf", "hf-mirror", "ms", "github"}.issubset(names)


def test_rank_sources_sorts_success_before_failure(monkeypatch):
    def fake_get(url, **kwargs):
        if "hf-mirror" in url:
            raise TimeoutError("slow")
        return FakeResponse(200)

    monkeypatch.setattr("modely.sources.requests.get", fake_get)
    results = rank_sources(candidates=["hf", "hf-mirror"], timeout=0.01)
    assert results[0].ok is True
    assert results[-1].ok is False
