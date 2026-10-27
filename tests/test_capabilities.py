"""Unit tests for backend capability reporting."""

from modely.backends import get_backend_capabilities, list_backends, print_backend_capabilities


def test_list_backends_includes_core_sources():
    sources = {item.source for item in list_backends()}
    assert {"hf", "ms", "github", "kaggle"}.issubset(sources)


def test_get_backend_capabilities_accepts_alias():
    capability = get_backend_capabilities("hf")
    assert capability.name == "hf-sdk"
    assert capability.supports["single_file"] is True
    assert capability.supports["snapshot"] is True


def test_print_backend_capabilities_includes_headers(capsys):
    print_backend_capabilities(get_backend_capabilities("kaggle"))

    output = capsys.readouterr().out
    assert "Backend" in output
    assert "Source" in output
    assert "Kind" in output
    assert "Status" in output
    assert "kaggle-api" in output
    assert "unavailable (requires: kaggle)" in output
    assert "Supports:" in output
