from fastapi import APIRouter

from api._common import ok

router = APIRouter()


def _postgres_ok() -> bool:
    try:
        from sqlalchemy import text
        from db.session import create_db_session
        with create_db_session() as s:
            s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _ollama_ok() -> bool:
    try:
        import httpx
        from config.settings import get_settings
        base = get_settings().llm_base_url.rstrip("/")
        resp = httpx.get(f"{base}/models", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@router.get("/health")
def health() -> dict:
    return ok(
        {
            "status": "ok",
            "postgres": _postgres_ok(),
            "ollama": _ollama_ok(),
        }
    )
