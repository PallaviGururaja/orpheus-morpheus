"""Shared test fixtures.

Tests run against the REAL production PostgreSQL driver (from .env) and the REAL
local Ollama model — never a SQLite substitute or a stubbed LLM. The DB is cleaned
between tests by truncating the app tables. Tests skip cleanly when PostgreSQL or
the Ollama model is genuinely unreachable.
"""
import httpx
import pytest


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    import config.settings as m
    m._settings = None
    yield
    m._settings = None


def _db_reachable() -> bool:
    try:
        from sqlalchemy import text
        from db.session import create_db_session
        with create_db_session() as s:
            s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _clean_db():
    """Truncate app tables before each test. Skips if PostgreSQL is unreachable."""
    if not _db_reachable():
        pytest.skip("PostgreSQL not reachable (AGENT_DATABASE_URL) — real DB required")
    from sqlalchemy import text
    from db.session import create_db_session

    def _truncate():
        with create_db_session() as s:
            s.execute(text("TRUNCATE TABLE queries, datasets, sessions CASCADE"))

    _truncate()
    yield
    _truncate()


def _ollama_model_ready() -> bool:
    """True only if the configured Ollama model is actually present and reachable."""
    try:
        from config.settings import get_settings
        s = get_settings()
        base = s.llm_base_url.rstrip("/")
        resp = httpx.get(f"{base}/models", timeout=3.0)
        if resp.status_code != 200:
            return False
        data = resp.json().get("data") or []
        names = {m.get("id", "") for m in data}
        model = s.llm_model
        return any(model == n or n.startswith(model.split(":")[0]) for n in names)
    except Exception:
        return False


@pytest.fixture
def _require_ollama():
    if not _ollama_model_ready():
        pytest.skip(
            "Ollama model not reachable/ready (still pulling?) — real local LLM required"
        )


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from api import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_csv_bytes() -> bytes:
    return (
        "region,revenue,units\n"
        "West,100,4\n"
        "East,200,7\n"
        "West,150,5\n"
        "East,50,2\n"
        "North,300,9\n"
    ).encode("utf-8")
