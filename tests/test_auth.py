"""Unit tests for auth helper behavior."""

from modely import auth


def test_get_token_prefers_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(auth.cache, "CONFIG_FILE", str(tmp_path / "config.json"))
    auth.save_token("hf", "stored")
    monkeypatch.setenv("HF_TOKEN", "env")
    assert auth.get_token("hf", "explicit") == "explicit"


def test_get_token_uses_env_before_config(monkeypatch, tmp_path):
    monkeypatch.setattr(auth.cache, "CONFIG_FILE", str(tmp_path / "config.json"))
    auth.save_token("hf", "stored")
    monkeypatch.setenv("HF_TOKEN", "env")
    assert auth.get_token("hf") == "env"


def test_save_and_delete_token(monkeypatch, tmp_path):
    monkeypatch.setattr(auth.cache, "CONFIG_FILE", str(tmp_path / "config.json"))
    auth.save_token("github", "tok")
    assert auth.get_token("github") == "tok"
    assert auth.delete_token("github") is True
    assert auth.get_token("github") is None


def test_whoami_without_token(monkeypatch, tmp_path):
    monkeypatch.setattr(auth.cache, "CONFIG_FILE", str(tmp_path / "config.json"))
    assert auth.whoami("ms") == "No token configured"
