from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # Storage — local PostgreSQL (audit trail / history)
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/data_analyst"
    )
    log_level: str = Field(default="INFO")

    # LLM — fully local via Ollama (OpenAI-compatible endpoint, no API key)
    llm_provider: str = Field(default="ollama")   # "ollama" | "anthropic" | "gemini"
    llm_base_url: str = Field(default="http://localhost:11434/v1")
    llm_model: str = Field(default="qwen2.5-coder:7b")

    # Cloud provider keys — intentionally unused when provider is "ollama"
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")

    # On-disk dataset store
    dataset_store: str = Field(default="./data/datasets")

    # Agent loop bound
    max_steps: int = Field(default=6)

    # Fast mode: skip the separate LLM "plan" call and let write_code work
    # directly from the profile + question. Halves latency on slow local CPUs
    # at a small cost to strategy on very complex questions.
    fast_mode: bool = Field(default=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
