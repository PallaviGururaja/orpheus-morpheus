"""POST /queries/{id}/rerun — execute edited code, record a NEW is_rerun audit row."""
from db.models import Query
from db.session import create_db_session



def _seed_completed_query(session_id: str, dataset_id: str) -> str:
    """Insert a completed original query to rerun against."""
    with create_db_session() as s:
        row = Query(
            session_id=session_id,
            dataset_ids=[dataset_id],
            question="What is the total revenue by region?",
            code="result = df.groupby('region')['revenue'].sum().reset_index()",
            answer_text="West leads with 250.",
            status="completed",
            verified=True,
            steps_used=2,
        )
        s.add(row)
        s.flush()
        return row.id


def test_rerun_records_new_audit_row(api_client, sample_csv_bytes, _require_ollama, upload):
    up = upload(sample_csv_bytes)
    original_id = _seed_completed_query(up["session_id"], up["dataset_id"])

    edited = "result = df.groupby('region')['units'].sum().reset_index()"
    r = api_client.post(f"/queries/{original_id}/rerun", json={"code": edited})
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["query_id"] != original_id  # a NEW row, not a mutation
    assert data["code"] == edited
    assert data["steps_used"] == 1
    assert data["result_table"]
    assert data["answer_text"]

    # New row is persisted as a rerun; original is untouched.
    with create_db_session() as s:
        new_row = s.get(Query, data["query_id"])
        assert new_row.is_rerun is True
        assert new_row.status == "completed"
        assert new_row.code == edited
        original = s.get(Query, original_id)
        assert original.is_rerun is False
        assert original.code == "result = df.groupby('region')['revenue'].sum().reset_index()"

    # The edited grouping (units) is reflected in the result.
    regions = {row["region"] for row in data["result_table"]}
    assert {"West", "East", "North"} <= regions


def test_rerun_scalar_result(api_client, sample_csv_bytes, upload):
    """Edge case: a scalar result serialises to a single-value table."""
    up = upload(sample_csv_bytes)
    original_id = _seed_completed_query(up["session_id"], up["dataset_id"])

    r = api_client.post(
        f"/queries/{original_id}/rerun",
        json={"code": "result = int(df['revenue'].sum())"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["result_table"] == [{"value": 800}]


def test_rerun_unknown_query_404(api_client):
    r = api_client.post("/queries/does-not-exist/rerun", json={"code": "result = 1"})
    assert r.status_code == 404


def test_rerun_empty_code_400(api_client, sample_csv_bytes, upload):
    up = upload(sample_csv_bytes)
    original_id = _seed_completed_query(up["session_id"], up["dataset_id"])
    r = api_client.post(f"/queries/{original_id}/rerun", json={"code": "   "})
    assert r.status_code == 400


def test_rerun_bad_code_returns_400(api_client, sample_csv_bytes, upload):
    """Error path: code that raises in the sandbox returns 400 with the error."""
    up = upload(sample_csv_bytes)
    original_id = _seed_completed_query(up["session_id"], up["dataset_id"])
    r = api_client.post(
        f"/queries/{original_id}/rerun",
        json={"code": "result = df['no_such_column'].sum()"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["message"]
