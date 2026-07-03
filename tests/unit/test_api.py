"""API contract tests — no LLM invoked (upload/profile/audit/stubs only)."""


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == "ok"
    assert "postgres" in body and "ollama" in body


def test_upload_csv_returns_profile(api_client, sample_csv_bytes):
    r = api_client.post(
        "/datasets",
        files={"file": ("sales.csv", sample_csv_bytes, "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 5
    assert data["column_count"] == 3
    assert data["session_id"] and data["dataset_id"]
    names = {c["name"] for c in data["profile"]["columns"]}
    assert {"region", "revenue", "units"} <= names


def test_upload_rejects_non_csv(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_rejects_empty(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert r.status_code == 400


def test_ask_missing_question_400(api_client, sample_csv_bytes):
    up = api_client.post(
        "/datasets", files={"file": ("s.csv", sample_csv_bytes, "text/csv")}
    ).json()["data"]
    r = api_client.post(
        "/ask",
        json={"session_id": up["session_id"], "dataset_ids": [up["dataset_id"]], "question": "  "},
    )
    assert r.status_code == 400


def test_ask_unknown_dataset_400(api_client, sample_csv_bytes):
    up = api_client.post(
        "/datasets", files={"file": ("s.csv", sample_csv_bytes, "text/csv")}
    ).json()["data"]
    r = api_client.post(
        "/ask",
        json={"session_id": up["session_id"], "dataset_ids": ["does-not-exist"], "question": "x?"},
    )
    assert r.status_code == 400


def test_get_query_not_found(api_client):
    r = api_client.get("/queries/nope")
    assert r.status_code == 404


def test_session_queries_not_found(api_client):
    r = api_client.get("/sessions/nope/queries")
    assert r.status_code == 404


def test_phase2_stream_implemented(api_client):
    # /ask/stream ships in Phase 2 — it is no longer a 501 stub. Called with no
    # params it fails validation (422 missing query params), never 501.
    r = api_client.get("/ask/stream")
    assert r.status_code != 501


def test_phase3_stub_501(api_client):
    r = api_client.get("/sessions")
    assert r.status_code == 501
