"""Full-pipeline integration tests — REAL Ollama + REAL PostgreSQL.

These skip cleanly (never stub) when the local Ollama model is genuinely
unreachable/still pulling. Everything else in the suite stays green.
"""
import pandas as pd
import pytest

from db.models import Query
from db.session import create_db_session


def _upload(api_client, csv_bytes) -> dict:
    r = api_client.post(
        "/datasets", files={"file": ("sales.csv", csv_bytes, "text/csv")}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.usefixtures("_require_ollama")
def test_ask_total_matches_hand_computed(api_client, sample_csv_bytes):
    up = _upload(api_client, sample_csv_bytes)

    # hand-computed ground truth
    expected_total = int(
        pd.read_csv(pd.io.common.BytesIO(sample_csv_bytes))["revenue"].sum()
    )
    assert expected_total == 800

    r = api_client.post(
        "/ask",
        json={
            "session_id": up["session_id"],
            "dataset_ids": [up["dataset_id"]],
            "question": "What is the total revenue across all rows? Return a single number.",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    # The answer's key number must reconcile with the hand-computed value.
    flat = [v for row in data["result_table"] for v in row.values()]
    assert any(
        isinstance(v, (int, float)) and abs(float(v) - expected_total) < 1e-6 for v in flat
    ) or (str(expected_total) in (data["answer_text"] or "")), (
        f"answer did not contain {expected_total}: {data}"
    )
    assert data["code"]  # generated python is present

    # Audit row persisted with code + result.
    with create_db_session() as s:
        q = s.get(Query, data["query_id"])
        assert q is not None
        assert q.code
        assert q.status in ("completed", "failed")
        assert q.result_table is not None


@pytest.mark.usefixtures("_require_ollama")
def test_ask_persists_audit_and_is_retrievable(api_client, sample_csv_bytes):
    up = _upload(api_client, sample_csv_bytes)
    r = api_client.post(
        "/ask",
        json={
            "session_id": up["session_id"],
            "dataset_ids": [up["dataset_id"]],
            "question": "What is the total revenue by region?",
        },
    )
    assert r.status_code == 200, r.text
    qid = r.json()["data"]["query_id"]

    rec = api_client.get(f"/queries/{qid}")
    assert rec.status_code == 200
    body = rec.json()["data"]
    assert body["question"] == "What is the total revenue by region?"
    assert body["code"]
    assert body["elapsed_ms"] is not None

    lst = api_client.get(f"/sessions/{up['session_id']}/queries")
    assert lst.status_code == 200
    assert any(q["query_id"] == qid for q in lst.json()["data"]["queries"])


@pytest.mark.usefixtures("_require_ollama")
def test_ask_reproducible(api_client, sample_csv_bytes):
    """Same question on same data yields the same headline number."""
    up = _upload(api_client, sample_csv_bytes)
    payload = {
        "session_id": up["session_id"],
        "dataset_ids": [up["dataset_id"]],
        "question": "What is the total revenue across all rows? Return a single number.",
    }
    nums = []
    for _ in range(2):
        r = api_client.post("/ask", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        flat = [
            float(v)
            for row in data["result_table"]
            for v in row.values()
            if isinstance(v, (int, float))
        ]
        nums.append(max(flat) if flat else None)
    assert nums[0] == nums[1] == 800.0
