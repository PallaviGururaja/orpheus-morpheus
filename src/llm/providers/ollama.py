"""Local Ollama provider via the OpenAI-compatible /v1/chat/completions API.

Fully local — hits AGENT_LLM_BASE_URL with AGENT_LLM_MODEL and no real API key
(Ollama ignores the key; we pass a dummy value the OpenAI client requires).
"""
from openai import OpenAI


class OllamaProvider:
    DEFAULT_MODEL = "qwen2.5-coder:7b"
    DEFAULT_BASE_URL = "http://localhost:11434/v1"

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._model = model or self.DEFAULT_MODEL
        # Ollama needs no key; the OpenAI client requires a non-empty string.
        self._client = OpenAI(base_url=self._base_url, api_key="ollama")
        self.last_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

    def call_model(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 700
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.0,
            max_tokens=max_tokens,  # cap generation — big latency win on CPU
            # Keep the model resident for 30 min so it isn't reloaded between the
            # two calls of a question (or between questions). Ollama-specific.
            extra_body={"keep_alive": "30m"},
        )
        usage = getattr(resp, "usage", None)
        self.last_usage = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        }
        return resp.choices[0].message.content or ""
