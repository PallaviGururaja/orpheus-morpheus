"""Orchestrates one analysis run: seed state, invoke the graph, persist the audit row.

Provides both the blocking ``run_analysis`` (POST /ask) and the streaming
``stream_analysis`` generator (GET /ask/stream), which share the seed/persist
helpers so the graph topology is identical either way.
"""
import time
from collections.abc import Iterator
from datetime import datetime, timezone

from db.models import Dataset, Query, Session as SessionRow
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.state import AgentState
from config.settings import get_settings
from observability.events import get_logger

_log = get_logger("runner")


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama model is unreachable."""


def _is_connection_error(text: str | None) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(
        k in low
        for k in ("connection", "connect", "refused", "timed out", "timeout",
                  "apiconnectionerror", "max retries", "failed to establish")
    )


def _load_session_messages(session_id: str, limit: int = 6) -> list[dict]:
    with create_db_session() as session:
        rows = (
            session.query(Query)
            .filter(Query.session_id == session_id, Query.status == "completed")
            .order_by(Query.created_at.desc())
            .limit(limit)
            .all()
        )
        # Extract values while still bound to the session (avoid detached refresh).
        pairs = [(r.question, r.answer_text) for r in rows]

    messages: list[dict] = []
    for question, answer in reversed(pairs):
        messages.append({"role": "user", "content": question})
        if answer:
            messages.append({"role": "assistant", "content": answer})
    return messages


def _create_pending(session_id: str, dataset_ids: list[str], question: str) -> tuple[str, dict]:
    """Create the pending audit row and return (run_id, dataset profile)."""
    with create_db_session() as session:
        ds = session.get(Dataset, dataset_ids[0]) if dataset_ids else None
        if ds is None:
            raise ValueError("Unknown dataset")
        profile = ds.profile or {}
        run = Query(
            session_id=session_id,
            dataset_ids=dataset_ids,
            question=question,
            status="pending",
        )
        session.add(run)
        session.flush()
        run_id = run.id
        sess = session.get(SessionRow, session_id)
        if sess is not None:
            sess.updated_at = datetime.now(timezone.utc)
    return run_id, profile


def _seed_state(
    run_id: str,
    session_id: str,
    dataset_ids: list[str],
    question: str,
    profile: dict,
    messages: list[dict],
    max_steps: int,
) -> AgentState:
    return {
        "run_id": run_id,
        "session_id": session_id,
        "dataset_ids": dataset_ids,
        "question": question,
        "profile": profile,
        "messages": messages,
        "max_steps": max_steps,
        "step": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "error": None,
    }


def _persist_final(run_id: str, final: AgentState, elapsed_ms: int) -> None:
    """Write the completed/failed audit row from the final graph state."""
    status = final.get("status", "failed")
    error = final.get("error")
    with create_db_session() as session:
        run = session.get(Query, run_id)
        if run is None:
            return
        run.plan = final.get("plan")
        run.code = final.get("code")
        run.result_table = final.get("result_table")
        run.answer_text = final.get("answer_text")
        run.chart_spec = final.get("chart_spec")
        run.verified = bool(final.get("verified", False))
        run.status = status
        run.error_message = error
        run.steps_used = final.get("step")
        run.prompt_tokens = final.get("prompt_tokens", 0)
        run.completion_tokens = final.get("completion_tokens", 0)
        run.elapsed_ms = elapsed_ms
        run.completed_at = datetime.now(timezone.utc)
    _log.info("run.complete", run_id=run_id, status=status, elapsed_ms=elapsed_ms,
              steps=final.get("step"))


def _build_payload(run_id: str, final: AgentState, elapsed_ms: int) -> dict:
    return {
        "query_id": run_id,
        "answer_text": final.get("answer_text"),
        "result_table": final.get("result_table", []),
        "chart_spec": final.get("chart_spec"),
        "code": final.get("code"),
        "verified": bool(final.get("verified", False)),
        "status": final.get("status", "failed"),
        "error": final.get("error"),
        "steps_used": final.get("step"),
        "prompt_tokens": final.get("prompt_tokens", 0),
        "completion_tokens": final.get("completion_tokens", 0),
        "elapsed_ms": elapsed_ms,
    }


def mark_run_failed(run_id: str | None, message: str) -> None:
    """Mark one pending run as failed (used when a stream is abandoned mid-run)."""
    if not run_id:
        return
    try:
        with create_db_session() as session:
            run = session.get(Query, run_id)
            if run is not None and run.status == "pending":
                run.status = "failed"
                run.error_message = message
                run.completed_at = datetime.now(timezone.utc)
                _log.info("run.marked_failed", run_id=run_id, reason=message)
    except Exception as exc:  # noqa: BLE001
        _log.error("run.mark_failed.error", run_id=run_id, error=str(exc))


def mark_session_pending_failed(session_id: str, message: str) -> int:
    """Mark every pending run in a session failed. Used to reclaim a stale lock."""
    count = 0
    try:
        with create_db_session() as session:
            rows = (
                session.query(Query)
                .filter(Query.session_id == session_id, Query.status == "pending")
                .all()
            )
            for run in rows:
                run.status = "failed"
                run.error_message = message
                run.completed_at = datetime.now(timezone.utc)
                count += 1
    except Exception as exc:  # noqa: BLE001
        _log.error("session.pending_failed.error", session_id=session_id, error=str(exc))
    if count:
        _log.info("session.pending_reclaimed", session_id=session_id, count=count)
    return count


def run_analysis(session_id: str, dataset_ids: list[str], question: str) -> dict:
    """Run the agent for one question. Returns a dict shaped for the /ask response."""
    settings = get_settings()
    run_id, profile = _create_pending(session_id, dataset_ids, question)
    messages = _load_session_messages(session_id)
    initial = _seed_state(
        run_id, session_id, dataset_ids, question, profile, messages, settings.max_steps
    )

    start = time.perf_counter()
    final: AgentState = agentic_ai.invoke(initial)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    _persist_final(run_id, final, elapsed_ms)

    status = final.get("status", "failed")
    error = final.get("error")
    if status == "failed" and _is_connection_error(error):
        raise OllamaUnavailable(error or "local model unavailable")

    return _build_payload(run_id, final, elapsed_ms)


def _iter_answer_chunks(text: str, size: int = 24) -> Iterator[str]:
    if not text:
        return
    for i in range(0, len(text), size):
        yield text[i : i + size]


def stream_analysis(
    session_id: str, dataset_ids: list[str], question: str
) -> Iterator[tuple[str, dict]]:
    """Run the SAME graph via a runner-level wrapper over ``agentic_ai.stream``.

    Yields ``(event_type, data)`` tuples: ``step`` per node transition, then
    ``token`` chunks of the answer, then a terminal ``done`` or ``error`` event.
    If the generator is closed early (client disconnect), the pending run is
    marked ``failed`` so the concurrency lock is never stranded.
    """
    settings = get_settings()
    run_id, profile = _create_pending(session_id, dataset_ids, question)
    messages = _load_session_messages(session_id)
    initial = _seed_state(
        run_id, session_id, dataset_ids, question, profile, messages, settings.max_steps
    )

    start = time.perf_counter()
    accumulated: dict = dict(initial)
    completed = False
    try:
        step_no = 0
        for update in agentic_ai.stream(initial, stream_mode="updates"):
            for node, node_state in update.items():
                if isinstance(node_state, dict):
                    accumulated.update(node_state)
                step_no += 1
                yield (
                    "step",
                    {
                        "step": step_no,
                        "total_estimate": settings.max_steps,
                        "node": node,
                        "elapsed_ms": int((time.perf_counter() - start) * 1000),
                    },
                )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _persist_final(run_id, accumulated, elapsed_ms)

        status = accumulated.get("status", "failed")
        error = accumulated.get("error")
        if status != "completed":
            if _is_connection_error(error):
                yield (
                    "error",
                    {
                        "code": "MODEL_UNAVAILABLE",
                        "message": error or "local model unavailable — is Ollama running?",
                    },
                )
            else:
                yield ("error", {"code": "INTERNAL", "message": error or "Analysis failed."})
            completed = True
            return

        payload = _build_payload(run_id, accumulated, elapsed_ms)
        for chunk in _iter_answer_chunks(payload.get("answer_text") or ""):
            yield ("token", {"text": chunk})
        yield ("done", payload)
        completed = True
    finally:
        if not completed:
            mark_run_failed(run_id, "Run interrupted (client disconnected).")
