"""Ask endpoints — runs the analysis agent for one question.

Holds the per-session concurrency lock shared by ``POST /ask``,
``GET /ask/stream`` and ``POST /queries/{id}/rerun``. The lock is
**reclaimable**: a holder whose run has been abandoned (client disconnected /
exceeded the run timeout) is marked ``failed`` and its lock released so a new
request proceeds instead of returning 409 forever.
"""
import threading
import time

from fastapi import APIRouter, Depends, Query as QueryParam
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Dataset, Session as SessionRow
from db.session import get_session
from domain.schemas import AskRequest
from graph.runner import (
    OllamaUnavailable,
    mark_session_pending_failed,
    run_analysis,
    stream_analysis,
)
from observability.events import get_logger, sse_frame

router = APIRouter()
_log = get_logger("api.ask")

# Single-user local tool: one run at a time per session.
# session_id -> {"started": monotonic_seconds}. A holder older than the run
# timeout is treated as abandoned and reclaimed on the next request.
_running_sessions: dict[str, dict] = {}
_lock = threading.Lock()
_RUN_TIMEOUT_SECONDS = 180.0


def _reclaim_stale_locked(session_id: str) -> None:
    """If the current holder is stale, fail its pending run and free the lock.

    Caller must hold ``_lock``.
    """
    entry = _running_sessions.get(session_id)
    if entry is None:
        return
    if time.monotonic() - entry["started"] >= _RUN_TIMEOUT_SECONDS:
        mark_session_pending_failed(
            session_id, "Run abandoned (client disconnected or exceeded timeout)."
        )
        _running_sessions.pop(session_id, None)
        _log.info("ask.lock_reclaimed", session_id=session_id)


def acquire_session(session_id: str) -> bool:
    """Acquire the per-session lock, reclaiming a stale holder first. False if a
    genuinely live run holds it."""
    with _lock:
        _reclaim_stale_locked(session_id)
        if session_id in _running_sessions:
            return False
        _running_sessions[session_id] = {"started": time.monotonic()}
        return True


def release_session(session_id: str) -> None:
    with _lock:
        _running_sessions.pop(session_id, None)


def _resolve_dataset_ids(
    session: Session, session_id: str, dataset_ids: list[str]
) -> list[str]:
    """Validate the session + datasets and default to all session datasets. Raises api_error."""
    sess = session.get(SessionRow, session_id)
    if sess is None:
        raise api_error("BAD_REQUEST", "Unknown session.", 400)

    if not dataset_ids:
        dataset_ids = [
            d.id
            for d in session.query(Dataset).filter(Dataset.session_id == session_id).all()
        ]
    if not dataset_ids:
        raise api_error("BAD_REQUEST", "No dataset in scope for this session.", 400)
    for did in dataset_ids:
        if session.get(Dataset, did) is None:
            raise api_error("BAD_REQUEST", f"Unknown dataset: {did}", 400)
    return dataset_ids


@router.post("/ask")
def ask(req: AskRequest, session: Session = Depends(get_session)) -> dict:
    if not req.question or not req.question.strip():
        raise api_error("BAD_REQUEST", "A question is required.", 400)

    dataset_ids = _resolve_dataset_ids(session, req.session_id, req.dataset_ids)

    if not acquire_session(req.session_id):
        raise api_error(
            "CONFLICT", "A run is already in progress for this session.", 409
        )

    try:
        result = run_analysis(req.session_id, dataset_ids, req.question)
    except OllamaUnavailable:
        raise api_error(
            "MODEL_UNAVAILABLE", "local model unavailable — is Ollama running?", 503
        )
    except ValueError as exc:
        raise api_error("BAD_REQUEST", str(exc), 400)
    except Exception as exc:  # noqa: BLE001
        _log.error("ask.unhandled", session_id=req.session_id, error=str(exc))
        raise api_error("INTERNAL", f"Analysis failed: {exc}", 500)
    finally:
        release_session(req.session_id)

    return ok(
        {
            "query_id": result["query_id"],
            "answer_text": result["answer_text"],
            "result_table": result["result_table"],
            "chart_spec": result["chart_spec"],
            "code": result["code"],
            "verified": result["verified"],
            "steps_used": result["steps_used"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "elapsed_ms": result["elapsed_ms"],
        }
    )


def _split_dataset_ids(raw: list[str] | None) -> list[str]:
    """Accept repeated or comma-separated ``dataset_ids`` query params."""
    out: list[str] = []
    for value in raw or []:
        out.extend(part for part in value.split(",") if part)
    return out


@router.get("/ask/stream")
def ask_stream(
    session_id: str,
    question: str,
    dataset_ids: list[str] | None = QueryParam(default=None),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    if not question or not question.strip():
        raise api_error("BAD_REQUEST", "A question is required.", 400)

    resolved = _resolve_dataset_ids(session, session_id, _split_dataset_ids(dataset_ids))

    def _event_stream():
        if not acquire_session(session_id):
            yield sse_frame(
                "error",
                {"code": "CONFLICT", "message": "A run is already in progress for this session."},
            )
            return
        try:
            for event_type, data in stream_analysis(session_id, resolved, question):
                yield sse_frame(event_type, data)
        except Exception as exc:  # noqa: BLE001
            _log.error("ask_stream.unhandled", session_id=session_id, error=str(exc))
            yield sse_frame("error", {"code": "INTERNAL", "message": f"Analysis failed: {exc}"})
        finally:
            release_session(session_id)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
