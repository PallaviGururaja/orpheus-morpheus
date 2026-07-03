"""Phase 2 / Phase 3 endpoints — stubbed to 501 until their phase ships."""
from fastapi import APIRouter

from api._common import api_error

router = APIRouter()

_P2 = "This endpoint ships in Phase 2 — not yet implemented."
_P3 = "This endpoint ships in Phase 3 — not yet implemented."


@router.get("/ask/stream")
def ask_stream() -> dict:
    raise api_error("NOT_IMPLEMENTED", _P2, 501)


@router.post("/queries/{query_id}/rerun")
def rerun(query_id: str) -> dict:
    raise api_error("NOT_IMPLEMENTED", _P2, 501)


@router.get("/queries/{query_id}/followups")
def followups(query_id: str) -> dict:
    raise api_error("NOT_IMPLEMENTED", _P2, 501)


@router.post("/datasets/connect-db")
def connect_db() -> dict:
    raise api_error("NOT_IMPLEMENTED", _P3, 501)


@router.get("/queries/{query_id}/export.csv")
def export_csv(query_id: str) -> dict:
    raise api_error("NOT_IMPLEMENTED", _P3, 501)


@router.get("/sessions")
def list_sessions() -> dict:
    raise api_error("NOT_IMPLEMENTED", _P3, 501)
