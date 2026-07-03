"""Reclaimable per-session lock — a stale/abandoned run must not block forever.

Reproduces the bug where a mid-run client disconnect left status='pending'
forever and held the lock, so every later /ask returned a permanent 409.
"""
import time

from db.models import Query
from db.session import create_db_session

import api.ask as ask_mod


def _insert_pending_query(session_id: str, dataset_id: str) -> str:
    with create_db_session() as s:
        row = Query(
            session_id=session_id,
            dataset_ids=[dataset_id],
            question="stranded run",
            status="pending",
        )
        s.add(row)
        s.flush()
        return row.id


def test_acquire_reclaims_stale_lock(api_client, sample_csv_bytes, upload):
    """A stale holder is reclaimed: its pending run is failed and the lock freed."""
    up = upload(sample_csv_bytes)
    session_id = up["session_id"]
    pending_id = _insert_pending_query(session_id, up["dataset_id"])

    # Simulate an abandoned run holding the lock past the timeout.
    ask_mod._running_sessions[session_id] = {
        "started": time.monotonic() - (ask_mod._RUN_TIMEOUT_SECONDS + 60)
    }
    try:
        acquired = ask_mod.acquire_session(session_id)
        assert acquired is True  # stale holder reclaimed, not blocked
    finally:
        ask_mod.release_session(session_id)

    with create_db_session() as s:
        row = s.get(Query, pending_id)
        assert row.status == "failed"
        assert row.error_message
        assert row.completed_at is not None


def test_live_lock_blocks_new_ask_409(api_client, sample_csv_bytes, upload):
    """A genuinely live (recent) run still returns 409 — the lock isn't a free-for-all."""
    up = upload(sample_csv_bytes)
    session_id = up["session_id"]

    # A fresh holder — well within the timeout — is a real live run.
    ask_mod._running_sessions[session_id] = {"started": time.monotonic()}
    try:
        r = api_client.post(
            "/ask",
            json={
                "session_id": session_id,
                "dataset_ids": [up["dataset_id"]],
                "question": "total revenue?",
            },
        )
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "CONFLICT"
    finally:
        ask_mod.release_session(session_id)


def test_stale_lock_does_not_block_new_ask(
    api_client, sample_csv_bytes, _require_ollama, upload
):
    """End-to-end: after an abandoned run, the next /ask succeeds (no permanent 409)."""
    up = upload(sample_csv_bytes)
    session_id = up["session_id"]
    pending_id = _insert_pending_query(session_id, up["dataset_id"])

    # Strand the session exactly as a mid-run disconnect would.
    ask_mod._running_sessions[session_id] = {
        "started": time.monotonic() - (ask_mod._RUN_TIMEOUT_SECONDS + 60)
    }
    try:
        r = api_client.post(
            "/ask",
            json={
                "session_id": session_id,
                "dataset_ids": [up["dataset_id"]],
                "question": "What is the total revenue by region?",
            },
        )
        assert r.status_code == 200, r.text
    finally:
        ask_mod.release_session(session_id)

    # The abandoned run was marked failed when the lock was reclaimed.
    with create_db_session() as s:
        assert s.get(Query, pending_id).status == "failed"
