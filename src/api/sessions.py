"""Session resume endpoints — list resumable sessions and rehydrate one."""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Dataset, Query, Session as SessionRow
from db.session import get_session

router = APIRouter()


@router.get("/sessions")
def list_sessions(session: Session = Depends(get_session)) -> dict:
    """List resumable sessions with dataset/query counts for the session picker."""
    ds_counts = dict(
        session.query(Dataset.session_id, func.count(Dataset.id))
        .group_by(Dataset.session_id)
        .all()
    )
    q_counts = dict(
        session.query(Query.session_id, func.count(Query.id))
        .group_by(Query.session_id)
        .all()
    )

    rows = (
        session.query(SessionRow).order_by(SessionRow.updated_at.desc()).all()
    )
    return ok(
        {
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "dataset_count": int(ds_counts.get(s.id, 0)),
                    "query_count": int(q_counts.get(s.id, 0)),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in rows
            ]
        }
    )


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str, session: Session = Depends(get_session)
) -> dict:
    """Rehydrate a prior session — its datasets (with profiles) and query history."""
    sess = session.get(SessionRow, session_id)
    if sess is None:
        raise api_error("NOT_FOUND", f"No such session: {session_id}", 404)

    datasets = (
        session.query(Dataset)
        .filter(Dataset.session_id == session_id)
        .order_by(Dataset.created_at.asc())
        .all()
    )
    queries = (
        session.query(Query)
        .filter(Query.session_id == session_id)
        .order_by(Query.created_at.desc())
        .all()
    )

    return ok(
        {
            "session": {
                "id": sess.id,
                "title": sess.title,
                "created_at": sess.created_at.isoformat() if sess.created_at else None,
                "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
            },
            "datasets": [
                {
                    "session_id": d.session_id,
                    "dataset_id": d.id,
                    "name": d.name,
                    "row_count": d.row_count,
                    "column_count": d.column_count,
                    "profile": d.profile,
                    "source_type": d.source_type,
                    "is_derived": d.is_derived,
                }
                for d in datasets
            ],
            "queries": [
                {
                    "query_id": q.id,
                    "question": q.question,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                    "verified": q.verified,
                    "status": q.status,
                }
                for q in queries
            ],
        }
    )
