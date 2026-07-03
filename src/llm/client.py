from config.settings import get_settings


def _make_provider():
    s = get_settings()
    provider = s.llm_provider

    # auto-detect from whichever key is set (cloud fallbacks; unused for this project)
    if not provider:
        if s.anthropic_api_key:
            provider = "anthropic"
        elif s.gemini_api_key:
            provider = "gemini"
        else:
            raise RuntimeError(
                "No LLM provider configured. Set AGENT_LLM_PROVIDER (e.g. 'ollama'), "
                "or an AGENT_ANTHROPIC_API_KEY / AGENT_GEMINI_API_KEY in .env."
            )

    if provider == "ollama":
        from llm.providers.ollama import OllamaProvider
        return OllamaProvider(base_url=s.llm_base_url, model=s.llm_model)
    if provider == "anthropic":
        from llm.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key=s.anthropic_api_key, model=s.llm_model)
    if provider == "gemini":
        from llm.providers.gemini import GeminiProvider
        return GeminiProvider(api_key=s.gemini_api_key, model=s.llm_model)

    raise RuntimeError(
        f"Unknown LLM provider: {provider!r}. Supported: ollama, anthropic, gemini"
    )


class LLMClient:
    def __init__(self) -> None:
        self._provider = _make_provider()

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        return self._provider.call_model(prompt, system=system)

    @property
    def last_usage(self) -> dict:
        return getattr(self._provider, "last_usage", {"prompt_tokens": 0, "completion_tokens": 0})
