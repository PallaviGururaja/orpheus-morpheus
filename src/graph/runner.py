"""Orchestrates one analysis run: seed state, invoke the graph, persist the audit row."""
import time
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


def run_analysis(session_id: str, dataset_ids: list[str], question: str) -> dict:
    """Run the agent for one question. Returns a dict shaped for the /ask response."""
    settings = get_settings()

    # Resolve the cached profile from the dataset row.
    with create_db_session() as session:
        ds = session.get(Dataset, dataset_ids[0]) if dataset_ids else None
        if ds is None:
            raise ValueError("Unknown dataset")
        profile = ds.profile or {}
        # Create the pending audit row.
        run = Query(
            session_id=session_id,
            dataset_ids=dataset_ids,
            question=question,
            status="pending",
        )
        session.add(run)
        session.flush()
        run_id = run.id
        # bump session activity
        sess = session.get(SessionRow, session_id)
        if sess is not None:
            sess.updated_at = datetime.now(timezone.utc)

    messages = _load_session_messages(session_id)

    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "dataset_ids": dataset_ids,
        "question": question,
        "profile": profile,
        "messages": messages,
        "max_steps": settings.max_steps,
        "step": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "error": None,
    }

    start = time.perf_counter()
    final: AgentState = agentic_ai.invoke(initial)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    status = final.get("status", "failed")
    error = final.get("error")

    # Persist the completed/failed audit row.
    with create_db_session() as session:
        run = session.get(Query, run_id)
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

    _log.info(
        "run.complete",
        run_id=run_id,
        status=status,
        elapsed_ms=elapsed_ms,
        steps=final.get("step"),
    )

    if status == "failed" and _is_connection_error(error):
        raise OllamaUnavailable(error or "local model unavailable")

    return {
        "query_id": run_id,
        "answer_text": final.get("answer_text"),
        "result_table": final.get("result_table", []),
        "chart_spec": final.get("chart_spec"),
        "code": final.get("code"),
        "verified": bool(final.get("verified", False)),
        "status": status,
        "error": error,
        "steps_used": final.get("step"),
        "prompt_tokens": final.get("prompt_tokens", 0),
        "completion_tokens": final.get("completion_tokens", 0),
        "elapsed_ms": elapsed_ms,
    }
