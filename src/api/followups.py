"""Follow-up suggestion endpoint (Phase 2).

Computed post-hoc from a completed query via the standalone ``generate_followups``
helper (not a graph node). Non-fatal: on model failure returns an empty list.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Dataset, Query
from db.session import get_session
from graph.followups import generate_followups

router = APIRouter()


@router.get("/queries/{query_id}/followups")
def followups(query_id: str, session: Session = Depends(get_session)) -> dict:
    q = session.get(Query, query_id)
    if q is None:
        raise api_error("NOT_FOUND", f"No such query: {query_id}", 404)

    profile: dict = {}
    if q.dataset_ids:
        ds = session.get(Dataset, q.dataset_ids[0])
        if ds is not None:
            profile = ds.profile or {}

    suggestions = generate_followups(q.question, q.answer_text or "", profile)
    return ok({"followups": suggestions})
