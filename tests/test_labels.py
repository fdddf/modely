"""Unit tests for local asset labels."""

from modely.labels import export_project, list_asset_metadata, update_asset_record


def test_update_asset_record_tags_and_project(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.labels.metadata_path", lambda: tmp_path / "asset_metadata.json")

    record = update_asset_record(
        "org/model",
        source="hf",
        repo_type="model",
        add_tags=["prod", "llm"],
        note="used by demo",
        favorite=True,
        status="approved",
        project="demo",
    )

    assert record["tags"] == ["llm", "prod"]
    assert record["favorite"] is True
    assert record["status"] == "approved"
    payload = list_asset_metadata(project="demo")
    assert "hf:model:org/model" in payload["resources"]
    assert payload["projects"]["demo"] == ["hf:model:org/model"]


def test_list_asset_metadata_filters_favorites(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.labels.metadata_path", lambda: tmp_path / "asset_metadata.json")
    update_asset_record("org/a", source="hf", repo_type="model", favorite=True)
    update_asset_record("org/b", source="hf", repo_type="dataset", favorite=False)

    payload = list_asset_metadata(favorites=True)

    assert list(payload["resources"]) == ["hf:model:org/a"]


def test_export_project_returns_shareable_resource_set(tmp_path, monkeypatch):
    monkeypatch.setattr("modely.labels.metadata_path", lambda: tmp_path / "asset_metadata.json")
    update_asset_record("org/model", source="hf", repo_type="model", add_tags=["approved"], project="team")

    payload = export_project("team")

    assert payload["project"] == "team"
    assert payload["count"] == 1
    assert payload["resources"][0]["key"] == "hf:model:org/model"
    assert payload["resources"][0]["tags"] == ["approved"]
