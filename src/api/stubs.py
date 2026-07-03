"""Phase 2 / Phase 3 endpoints — stubbed to 501 until their phase ships."""
from fastapi import APIRouter

from api._common import api_error

router = APIRouter()

_P3 = "This endpoint ships in Phase 3 — not yet implemented."

# Phase 2 endpoints (/ask/stream, /queries/{id}/rerun, /queries/{id}/followups)
# are now implemented in api.ask / api.rerun / api.followups.


@router.post("/datasets/connect-db")
def connect_db() -> dict:
    raise api_error("NOT_IMPLEMENTED", _P3, 501)


@router.get("/queries/{query_id}/export.csv")
def export_csv(query_id: str) -> dict:
    raise api_error("NOT_IMPLEMENTED", _P3, 501)


@router.get("/sessions")
def list_sessions() -> dict:
    raise api_error("NOT_IMPLEMENTED", _P3, 501)
