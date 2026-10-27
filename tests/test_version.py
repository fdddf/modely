"""Unit tests for resource revision diffs."""

from modely.types import FileInfo
from modely.version import diff_resource_revisions


def test_diff_resource_revisions(monkeypatch):
    def fake_list(ref, revision=None, **kwargs):
        if revision == "old":
            return [FileInfo("a.txt", size=1), FileInfo("b.txt", size=2)]
        return [FileInfo("b.txt", size=3), FileInfo("c.txt", size=4)]

    monkeypatch.setattr("modely.version.list_repo_files", fake_list)

    diff = diff_resource_revisions("hf://models/org/model", left_revision="old", right_revision="new")

    assert diff["summary"] == {"added": 1, "removed": 1, "changed": 1, "common": 1}
    assert diff["added"][0]["path"] == "c.txt"
    assert diff["removed"][0]["path"] == "a.txt"
    assert diff["changed"][0]["path"] == "b.txt"
