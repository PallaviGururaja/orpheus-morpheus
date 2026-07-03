"""Audit-trail retrieval endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Query, Session as SessionRow
from db.session import get_session

router = APIRouter()


def _query_to_dict(q: Query) -> dict:
    return {
        "query_id": q.id,
        "session_id": q.session_id,
        "dataset_ids": q.dataset_ids,
        "question": q.question,
        "plan": q.plan,
        "code": q.code,
        "result_table": q.result_table,
        "answer_text": q.answer_text,
        "chart_spec": q.chart_spec,
        "verified": q.verified,
        "status": q.status,
        "error_message": q.error_message,
        "steps_used": q.steps_used,
        "prompt_tokens": q.prompt_tokens,
        "completion_tokens": q.completion_tokens,
        "elapsed_ms": q.elapsed_ms,
        "is_rerun": q.is_rerun,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "completed_at": q.completed_at.isoformat() if q.completed_at else None,
    }


@router.get("/queries/{query_id}")
def get_query(query_id: str, session: Session = Depends(get_session)) -> dict:
    q = session.get(Query, query_id)
    if q is None:
        raise api_error("NOT_FOUND", f"No such query: {query_id}", 404)
    return ok(_query_to_dict(q))


@router.get("/sessions/{session_id}/queries")
def list_session_queries(
    session_id: str, session: Session = Depends(get_session)
) -> dict:
    sess = session.get(SessionRow, session_id)
    if sess is None:
        raise api_error("NOT_FOUND", f"No such session: {session_id}", 404)
    rows = (
        session.query(Query)
        .filter(Query.session_id == session_id)
        .order_by(Query.created_at.desc())
        .all()
    )
    return ok(
        {
            "queries": [
                {
                    "query_id": r.id,
                    "question": r.question,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "verified": r.verified,
                    "status": r.status,
                }
                for r in rows
            ]
        }
    )
