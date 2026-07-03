"""Settings + provider factory — no live LLM required."""
import pytest


def test_defaults_are_local(monkeypatch):
    monkeypatch.delenv("AGENT_LLM_PROVIDER", raising=False)
    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.llm_provider == "ollama"
    assert s.llm_base_url == "http://localhost:11434/v1"
    assert s.llm_model == "qwen2.5-coder:7b"
    assert s.database_url.startswith("postgresql+psycopg")


def test_ollama_provider_built():
    from llm.client import _make_provider
    from llm.providers.ollama import OllamaProvider
    provider = _make_provider()
    assert isinstance(provider, OllamaProvider)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "nope")
    import config.settings as m
    m._settings = None
    from llm.client import _make_provider
    with pytest.raises(RuntimeError, match="Unknown LLM provider"):
        _make_provider()
