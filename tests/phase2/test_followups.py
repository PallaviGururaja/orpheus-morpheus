"""GET /queries/{id}/followups — 2-3 suggested follow-ups (real Ollama)."""
from db.models import Query
from db.session import create_db_session



def _seed_completed_query(session_id: str, dataset_id: str, answer: str) -> str:
    with create_db_session() as s:
        row = Query(
            session_id=session_id,
            dataset_ids=[dataset_id],
            question="What is the total revenue by region?",
            code="result = df.groupby('region')['revenue'].sum().reset_index()",
            answer_text=answer,
            result_table=[{"region": "West", "revenue": 250}],
            status="completed",
            verified=True,
        )
        s.add(row)
        s.flush()
        return row.id


def test_followups_returns_suggestions(api_client, sample_csv_bytes, _require_ollama, upload):
    up = upload(sample_csv_bytes)
    qid = _seed_completed_query(
        up["session_id"], up["dataset_id"], "Total revenue is 800, led by West at 250."
    )

    r = api_client.get(f"/queries/{qid}/followups")
    assert r.status_code == 200, r.text
    followups = r.json()["data"]["followups"]
    assert isinstance(followups, list)
    assert 1 <= len(followups) <= 3
    assert all(isinstance(f, str) and f.strip() for f in followups)


def test_followups_empty_answer_still_ok(api_client, sample_csv_bytes, _require_ollama, upload):
    """Edge case: a query with an empty answer still returns a (possibly empty) list."""
    up = upload(sample_csv_bytes)
    qid = _seed_completed_query(up["session_id"], up["dataset_id"], "")

    r = api_client.get(f"/queries/{qid}/followups")
    assert r.status_code == 200, r.text
    followups = r.json()["data"]["followups"]
    assert isinstance(followups, list)
    assert len(followups) <= 3


def test_followups_unknown_query_404(api_client):
    """Error path: no such query."""
    r = api_client.get("/queries/does-not-exist/followups")
    assert r.status_code == 404
