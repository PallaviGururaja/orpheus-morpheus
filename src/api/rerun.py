"""Edit-and-rerun endpoint (Phase 2).

Executes user-edited Python against the same session/datasets in the same
restricted namespace as the original run, and records a NEW audit row
(``is_rerun=True``) rather than mutating the original — preserving the trail.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from analysis.charts import select_chart
from analysis.engine import load_csv
from analysis.executor import execute_python
from api._common import ok, api_error
from api.ask import acquire_session, release_session
from db.models import Dataset, Query
from db.session import get_session
from llm.client import LLMClient
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.rerun")
_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


class RerunRequest(BaseModel):
    code: str = ""


def _load_dataframe(session: Session, dataset_ids: list[str]):
    if not dataset_ids:
        raise api_error("BAD_REQUEST", "No dataset in scope for this query.", 400)
    ds = session.get(Dataset, dataset_ids[0])
    if ds is None:
        raise api_error("BAD_REQUEST", f"Unknown dataset: {dataset_ids[0]}", 400)
    return load_csv(ds.storage_path)


def _compose_answer(question: str, code: str, outcome: dict) -> tuple[str, dict]:
    """Regenerate a written answer from the new result. Falls back to a plain
    summary if the model is unreachable. Returns (answer_text, token usage)."""
    import json

    try:
        client = LLMClient()
        system = (_PROMPT_DIR / "verify.md").read_text(encoding="utf-8").strip()
        table_preview = json.dumps(outcome["result_table"][:20], default=str)
        prompt = (
            f"Question: {question}\n\n"
            f"Code that was run:\n{code}\n\n"
            f"Result repr:\n{outcome['result_repr']}\n\n"
            f"Result table (rows):\n{table_preview}\n\n"
            "Write the final answer."
        )
        answer = client.call_model(prompt, system=system)
        return answer.strip(), client.last_usage
    except Exception as exc:  # noqa: BLE001 — answer regeneration is non-fatal
        _log.error("rerun.compose_answer.error", error=str(exc))
        preview = outcome.get("result_repr") or "(no output)"
        return f"Rerun result: {preview}", {"prompt_tokens": 0, "completion_tokens": 0}


@router.post("/queries/{query_id}/rerun")
def rerun(
    query_id: str, req: RerunRequest, session: Session = Depends(get_session)
) -> dict:
    original = session.get(Query, query_id)
    if original is None:
        raise api_error("NOT_FOUND", f"No such query: {query_id}", 404)

    code = (req.code or "").strip()
    if not code:
        raise api_error("BAD_REQUEST", "Edited code is empty.", 400)

    session_id = original.session_id
    dataset_ids = list(original.dataset_ids or [])

    if not acquire_session(session_id):
        raise api_error(
            "CONFLICT", "A run is already in progress for this session.", 409
        )

    try:
        df = _load_dataframe(session, dataset_ids)
        start = time.perf_counter()
        outcome = execute_python(code, df)
        if outcome["exec_error"]:
            # Surface the sandbox error so the user can fix the edited code.
            raise api_error("BAD_REQUEST", outcome["exec_error"], 400)

        chart_spec = select_chart(outcome["result_table"])
        answer_text, usage = _compose_answer(original.question, code, outcome)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        new_run = Query(
            session_id=session_id,
            dataset_ids=dataset_ids,
            question=original.question,
            plan=None,
            code=code,
            result_table=outcome["result_table"],
            answer_text=answer_text,
            chart_spec=chart_spec,
            verified=bool(outcome["result_table"]),
            status="completed",
            steps_used=1,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            elapsed_ms=elapsed_ms,
            is_rerun=True,
            completed_at=datetime.now(timezone.utc),
        )
        session.add(new_run)
        session.flush()
        new_id = new_run.id
        _log.info("rerun.completed", original=query_id, new_query_id=new_id)

        payload = {
            "query_id": new_id,
            "answer_text": answer_text,
            "result_table": outcome["result_table"],
            "chart_spec": chart_spec,
            "code": code,
            "verified": bool(outcome["result_table"]),
            "steps_used": 1,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "elapsed_ms": elapsed_ms,
        }
    finally:
        release_session(session_id)

    return ok(payload)
