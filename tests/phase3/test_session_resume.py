"""Cross-day session resume — REAL PostgreSQL (production driver, from .env).

Seeds a session with two datasets and two queries directly via the production ORM
(no LLM needed — resume is deterministic DB read-back), then exercises the two
resume endpoints:
  - GET /sessions          → session appears with correct dataset/query counts
  - GET /sessions/{id}     → datasets (with profiles) + query history restored
  - GET /sessions/{id}     → 404 for an unknown id
"""
import pytest

from db.models import Dataset, Query, Session as SessionRow
from db.session import create_db_session


def _seed_session() -> dict:
    """Create one session with 2 datasets + 2 queries. Returns the ids/values."""
    with create_db_session() as s:
        sess = SessionRow(title="Sales analysis")
        s.add(sess)
        s.flush()
        sid = sess.id

        d1 = Dataset(
            session_id=sid,
            name="orders.csv",
            source_type="csv",
            storage_path="/tmp/orders.csv",
            row_count=12000,
            column_count=8,
            profile={"columns": [{"name": "region", "dtype": "string",
                                   "null_pct": 0.0, "distinct": 4}],
                     "duplicate_rows": 3, "flags": ["3 duplicate rows"]},
            is_derived=False,
        )
        d2 = Dataset(
            session_id=sid,
            name="customers.csv",
            source_type="csv",
            storage_path="/tmp/customers.csv",
            row_count=500,
            column_count=3,
            profile={"columns": [{"name": "segment", "dtype": "string",
                                   "null_pct": 0.0, "distinct": 2}],
                     "duplicate_rows": 0, "flags": []},
            is_derived=False,
        )
        s.add_all([d1, d2])
        s.flush()

        q1 = Query(
            session_id=sid,
            dataset_ids=[d1.id],
            question="total revenue by region",
            answer_text="West leads with 480K",
            verified=True,
            status="succeeded",
        )
        q2 = Query(
            session_id=sid,
            dataset_ids=[d1.id, d2.id],
            question="premium segment total",
            answer_text="475",
            verified=False,
            status="succeeded",
        )
        s.add_all([q1, q2])
        s.flush()

        info = {
            "session_id": sid,
            "dataset_ids": {d1.id, d2.id},
            "dataset_names": {d1.name, d2.name},
            "query_ids": {q1.id, q2.id},
            "questions": {q1.question, q2.question},
        }
        s.commit()
    return info


# --------------------------------------------------------------------------- #
# 1) Happy path — list shows the session with correct counts; detail restores it.
# --------------------------------------------------------------------------- #
def test_list_sessions_shows_counts(api_client):
    info = _seed_session()

    r = api_client.get("/sessions")
    assert r.status_code == 200, r.text
    sessions = r.json()["data"]["sessions"]
    match = [s for s in sessions if s["id"] == info["session_id"]]
    assert len(match) == 1, f"seeded session missing from list: {sessions}"
    row = match[0]
    assert row["title"] == "Sales analysis"
    assert row["dataset_count"] == 2
    assert row["query_count"] == 2
    assert row["updated_at"]


def test_get_session_detail_restores_datasets_and_history(api_client):
    info = _seed_session()

    r = api_client.get(f"/sessions/{info['session_id']}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["session"]["id"] == info["session_id"]
    assert data["session"]["title"] == "Sales analysis"

    # Datasets restored with ids, names, counts, and profiles.
    datasets = data["datasets"]
    assert len(datasets) == 2
    assert {d["dataset_id"] for d in datasets} == info["dataset_ids"]
    assert {d["name"] for d in datasets} == info["dataset_names"]
    orders = next(d for d in datasets if d["name"] == "orders.csv")
    assert orders["row_count"] == 12000
    assert orders["column_count"] == 8
    assert orders["source_type"] == "csv"
    assert orders["profile"]["columns"][0]["name"] == "region"

    # Query history restored with ids and question values.
    queries = data["queries"]
    assert len(queries) == 2
    assert {q["query_id"] for q in queries} == info["query_ids"]
    assert {q["question"] for q in queries} == info["questions"]


# --------------------------------------------------------------------------- #
# 2) Edge — a brand-new empty session lists with zero counts and empty detail.
# --------------------------------------------------------------------------- #
def test_empty_session_has_zero_counts(api_client):
    with create_db_session() as s:
        sess = SessionRow(title="Empty session")
        s.add(sess)
        s.flush()
        sid = sess.id
        s.commit()

    r = api_client.get("/sessions")
    assert r.status_code == 200, r.text
    row = next(s for s in r.json()["data"]["sessions"] if s["id"] == sid)
    assert row["dataset_count"] == 0
    assert row["query_count"] == 0

    r2 = api_client.get(f"/sessions/{sid}")
    assert r2.status_code == 200, r2.text
    data = r2.json()["data"]
    assert data["datasets"] == []
    assert data["queries"] == []


# --------------------------------------------------------------------------- #
# 3) Error path — unknown session id → 404.
# --------------------------------------------------------------------------- #
def test_get_unknown_session_is_404(api_client):
    r = api_client.get("/sessions/does-not-exist")
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "NOT_FOUND"
