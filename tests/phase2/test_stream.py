"""GET /ask/stream — SSE step trace + streamed answer (real Ollama + PostgreSQL)."""


def test_stream_happy_path_emits_steps_tokens_and_done(
    api_client, sample_csv_bytes, _require_ollama, upload, parse_sse
):
    up = upload(sample_csv_bytes)

    r = api_client.get(
        "/ask/stream",
        params={
            "session_id": up["session_id"],
            "dataset_ids": up["dataset_id"],
            "question": "What is the total revenue by region?",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(r.text)
    kinds = [e for e, _ in events]

    # Step events drive the "Step 3 of 6" counter — monotonic, with the budget.
    steps = [d for e, d in events if e == "step"]
    assert steps, f"expected step events, got {kinds}"
    assert all(s["total_estimate"] == 6 for s in steps)
    indices = [s["step"] for s in steps]
    assert indices == sorted(indices) and indices[0] == 1
    assert all("node" in s and "elapsed_ms" in s for s in steps)

    # Terminal event must be a successful done with the audit payload.
    assert kinds[-1] == "done", f"expected done last, got {kinds}"
    done = events[-1][1]
    assert done["query_id"]
    assert done["answer_text"]

    # Streamed tokens must reconstruct exactly the final answer.
    tokens = "".join(d["text"] for e, d in events if e == "token")
    assert tokens == done["answer_text"]

    # The persisted audit row matches the streamed answer.
    got = api_client.get(f"/queries/{done['query_id']}").json()["data"]
    assert got["status"] == "completed"
    assert got["answer_text"] == done["answer_text"]


def test_stream_defaults_dataset_ids_from_session(
    api_client, sample_csv_bytes, _require_ollama, upload, parse_sse
):
    """Edge case: dataset_ids omitted → defaults to all datasets in the session."""
    up = upload(sample_csv_bytes)

    r = api_client.get(
        "/ask/stream",
        params={"session_id": up["session_id"], "question": "How many rows are there?"},
    )
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    kinds = [e for e, _ in events]
    assert kinds[-1] in ("done", "error")
    if kinds[-1] == "done":
        assert events[-1][1]["query_id"]


def test_stream_missing_question_400(api_client, sample_csv_bytes, upload):
    """Error path: a blank question is rejected before any streaming begins."""
    up = upload(sample_csv_bytes)
    r = api_client.get(
        "/ask/stream",
        params={"session_id": up["session_id"], "dataset_ids": up["dataset_id"], "question": "  "},
    )
    assert r.status_code == 400


def test_stream_unknown_session_400(api_client):
    """Error path: unknown session id is rejected up front."""
    r = api_client.get(
        "/ask/stream",
        params={"session_id": "nope", "question": "anything?"},
    )
    assert r.status_code == 400
