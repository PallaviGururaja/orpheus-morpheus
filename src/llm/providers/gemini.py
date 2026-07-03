from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL
        self.last_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

    def call_model(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        # Disable "thinking" — gemini-2.5-flash otherwise spends the output-token
        # budget on hidden reasoning (truncating short replies) and is slower.
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        self.last_usage = {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "completion_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        }
        return response.text or ""
