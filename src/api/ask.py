"""Ask endpoint — runs the analysis agent for one question."""
import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Dataset, Session as SessionRow
from db.session import get_session
from domain.schemas import AskRequest
from graph.runner import run_analysis, OllamaUnavailable
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.ask")

# Single-user local tool: one run at a time per session.
_running_sessions: set[str] = set()
_lock = threading.Lock()


@router.post("/ask")
def ask(req: AskRequest, session: Session = Depends(get_session)) -> dict:
    if not req.question or not req.question.strip():
        raise api_error("BAD_REQUEST", "A question is required.", 400)

    sess = session.get(SessionRow, req.session_id)
    if sess is None:
        raise api_error("BAD_REQUEST", "Unknown session.", 400)

    dataset_ids = req.dataset_ids
    if not dataset_ids:
        # default to the session's datasets
        dataset_ids = [d.id for d in session.query(Dataset).filter(
            Dataset.session_id == req.session_id).all()]
    if not dataset_ids:
        raise api_error("BAD_REQUEST", "No dataset in scope for this session.", 400)
    for did in dataset_ids:
        if session.get(Dataset, did) is None:
            raise api_error("BAD_REQUEST", f"Unknown dataset: {did}", 400)

    with _lock:
        if req.session_id in _running_sessions:
            raise api_error(
                "CONFLICT", "A run is already in progress for this session.", 409
            )
        _running_sessions.add(req.session_id)

    try:
        result = run_analysis(req.session_id, dataset_ids, req.question)
    except OllamaUnavailable:
        raise api_error(
            "MODEL_UNAVAILABLE",
            "local model unavailable — is Ollama running?",
            503,
        )
    except ValueError as exc:
        raise api_error("BAD_REQUEST", str(exc), 400)
    except Exception as exc:  # noqa: BLE001
        _log.error("ask.unhandled", session_id=req.session_id, error=str(exc))
        raise api_error("INTERNAL", f"Analysis failed: {exc}", 500)
    finally:
        with _lock:
            _running_sessions.discard(req.session_id)

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
