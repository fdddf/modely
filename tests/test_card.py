"""Unit tests for card helpers."""

from modely.card import get_card, parse_card_text


def test_parse_card_frontmatter_scalars_and_lists():
    text = """---
license: apache-2.0
tags: nlp, text-generation
pipeline_tag: text-generation
---
# Model
"""
    data = parse_card_text(text)
    assert data["license"] == "apache-2.0"
    assert data["tags"] == ["nlp", "text-generation"]
    assert data["pipeline_tag"] == "text-generation"


def test_get_card_returns_warning_when_missing(monkeypatch):
    def fake_get(*args, **kwargs):
        raise RuntimeError("not found")

    monkeypatch.setattr("modely.card._get_hf_card", fake_get)
    card = get_card("hf://models/gpt2")
    assert card.text == ""
    assert card.warnings
