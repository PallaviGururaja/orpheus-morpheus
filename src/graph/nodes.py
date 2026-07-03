"""LangGraph nodes for the data-analysis agent.

The LLM client is instantiated lazily inside nodes so the graph compiles at import
time with no environment variables set.
"""
import json
import re
from pathlib import Path

from analysis.charts import select_chart
from analysis.engine import load_csv, load_tables, table_name_for
from analysis.executor import execute_python
from analysis.profiler import profile_dataframe
from db.models import Dataset
from db.session import create_db_session
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")


def _prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _accumulate_tokens(state: AgentState, client: LLMClient) -> dict:
    usage = client.last_usage
    return {
        "prompt_tokens": state.get("prompt_tokens", 0) + usage.get("prompt_tokens", 0),
        "completion_tokens": state.get("completion_tokens", 0)
        + usage.get("completion_tokens", 0),
    }


def _extract_code(text: str) -> str:
    """Pull the first fenced Python block; fall back to the raw text."""
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def _resolve_tables(dataset_ids: list[str]) -> list[dict]:
    """Load the in-scope dataset rows and assign each a stable table name.

    Returns an ordered list of ``{table_name, dataset_id, storage_path, profile,
    name}`` dicts — in ``dataset_ids`` order — so ``plan`` (profiles) and
    ``execute_code`` (DataFrames) agree on table names.
    """
    if not dataset_ids:
        raise ValueError("No dataset in scope for this question.")
    resolved: list[dict] = []
    taken: set[str] = set()
    with create_db_session() as session:
        for did in dataset_ids:
            ds = session.get(Dataset, did)
            if ds is None:
                raise ValueError(f"Unknown dataset: {did}")
            resolved.append(
                {
                    "table_name": table_name_for(ds.name, taken),
                    "dataset_id": ds.id,
                    "name": ds.name,
                    "storage_path": ds.storage_path,
                    "profile": ds.profile or {},
                }
            )
    return resolved


def _load_dataframe(dataset_ids: list[str]):
    """Back-compat single-dataset loader (first dataset only)."""
    if not dataset_ids:
        raise ValueError("No dataset in scope for this question.")
    with create_db_session() as session:
        ds = session.get(Dataset, dataset_ids[0])
        if ds is None:
            raise ValueError(f"Unknown dataset: {dataset_ids[0]}")
        path = ds.storage_path
    return load_csv(path)


def _load_dataframes(dataset_ids: list[str]) -> dict:
    """Resolve every in-scope dataset to a ``{table_name: DataFrame}`` map."""
    resolved = _resolve_tables(dataset_ids)
    return load_tables([(t["table_name"], t["storage_path"]) for t in resolved])


def _messages_context(state: AgentState) -> str:
    msgs = state.get("messages") or []
    if not msgs:
        return ""
    lines = [f"{m.get('role')}: {m.get('content')}" for m in msgs[-6:]]
    return "Prior conversation:\n" + "\n".join(lines) + "\n\n"


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def _profiles_prompt(profiles: dict) -> str:
    """Render one or many table profiles for the LLM prompt."""
    if len(profiles) == 1:
        (tname, prof), = profiles.items()
        return (
            f"Dataset table `{tname}` profile:\n{json.dumps(prof, default=str)}"
        )
    parts = ["You have MULTIPLE datasets loaded. Each is a table you can join/union/compare:"]
    for tname, prof in profiles.items():
        cols = [c.get("name") for c in prof.get("columns", [])]
        parts.append(
            f"- Table `{tname}` — {prof.get('row_count', '?')} rows, columns: {cols}"
        )
    parts.append("\nFull profiles:\n" + json.dumps(profiles, default=str))
    return "\n".join(parts)


def plan(state: AgentState) -> AgentState:
    try:
        # Phase 2: load EVERY in-scope dataset's cached profile, keyed by table name.
        profiles: dict = {}
        try:
            for t in _resolve_tables(state.get("dataset_ids", [])):
                profiles[t["table_name"]] = t["profile"]
        except Exception as exc:
            return {**state, "error": f"plan failed: {exc}"}

        client = LLMClient()
        multi = len(profiles) > 1
        selection_hint = (
            "\nName WHICH table(s) are relevant and, if more than one is needed, "
            "the JOIN or UNION key columns. Use only the datasets the question "
            "actually needs.\n"
            if multi
            else ""
        )
        prompt = (
            f"{_messages_context(state)}"
            f"{_profiles_prompt(profiles)}\n\n"
            f"Question: {state['question']}\n"
            f"{selection_hint}\nWrite the strategy."
        )
        plan_text = client.call_model(prompt, system=_prompt("plan.md"))
        _log.info(
            "node.plan",
            run_id=state.get("run_id"),
            step=1,
            tables=list(profiles.keys()),
        )
        return {
            **state,
            "plan": plan_text.strip(),
            "profiles": profiles,
            "step": 1,
            **_accumulate_tokens(state, client),
        }
    except Exception as exc:
        _log.error("node.plan.error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"plan failed: {exc}"}


def write_code(state: AgentState) -> AgentState:
    try:
        client = LLMClient()
        profiles = state.get("profiles") or {}
        if profiles:
            names = list(profiles.keys())
            if len(names) > 1:
                var_note = (
                    "The following pandas DataFrames are ALREADY loaded (do NOT read files) "
                    f"and also registered as DuckDB tables of the same name: {names}. "
                    "Join/union/compare them as the question requires. "
                    "To run SQL you MUST use the provided connection: `con.execute(sql).df()` "
                    "— do NOT call duckdb.query()/duckdb.sql(); only `con` has these tables. "
                    "Prefer pandas merges (e.g. a.merge(b, on='key')) when simpler.\n"
                )
            else:
                var_note = (
                    f"A pandas DataFrame `{names[0]}` (also available as `df`) is loaded, "
                    "and registered on the DuckDB connection `con` under both names. "
                    "For SQL use `con.execute(sql).df()`, not duckdb.query()/duckdb.sql().\n"
                )
            profile_block = var_note + "Profiles:\n" + json.dumps(profiles, default=str)
        else:
            profile_block = "Dataset profile:\n" + json.dumps(
                state.get("profile", {}), default=str
            )
        parts = [
            profile_block,
            f"Plan:\n{state.get('plan', '')}",
            f"Question: {state['question']}",
        ]
        if state.get("exec_error"):
            parts.append(
                "The previous attempt FAILED. Fix it.\n"
                f"Previous code:\n{state.get('code', '')}\n"
                f"Error:\n{state['exec_error']}"
            )
        prompt = "\n\n".join(parts) + "\n\nWrite the corrected Python code block."
        raw = client.call_model(prompt, system=_prompt("write_code.md"))
        code = _extract_code(raw)
        _log.info("node.write_code", run_id=state.get("run_id"), step=state.get("step"))
        return {**state, "code": code, **_accumulate_tokens(state, client)}
    except Exception as exc:
        _log.error("node.write_code.error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"write_code failed: {exc}"}


def execute_code(state: AgentState) -> AgentState:
    """Runs generated code in the restricted namespace. Never raises."""
    step = state.get("step", 1) + 1
    try:
        tables = _load_dataframes(state.get("dataset_ids", []))
    except Exception as exc:
        return {
            **state,
            "step": step,
            "exec_error": f"dataset load failed: {exc}",
            "exec_stdout": "",
            "result_repr": "",
            "result_table": [],
        }

    outcome = execute_python(state.get("code", ""), tables=tables)
    chart_spec = None
    if not outcome["exec_error"]:
        chart_spec = select_chart(outcome["result_table"])
    _log.info(
        "node.execute_code",
        run_id=state.get("run_id"),
        step=step,
        exec_error=outcome["exec_error"],
        rows=len(outcome["result_table"]),
    )
    return {
        **state,
        "step": step,
        "exec_stdout": outcome["exec_stdout"],
        "exec_error": outcome["exec_error"],
        "result_repr": outcome["result_repr"],
        "result_table": outcome["result_table"],
        "chart_spec": chart_spec,
    }


def inspect(state: AgentState) -> AgentState:
    """Routing-only node (routing done by the conditional edge)."""
    _log.info(
        "node.inspect",
        run_id=state.get("run_id"),
        step=state.get("step"),
        exec_error=state.get("exec_error"),
    )
    return state


def verify(state: AgentState) -> AgentState:
    """Compose the written answer and reconcile the headline numbers."""
    try:
        result_table = state.get("result_table", [])
        verified = bool(result_table) and not state.get("exec_error")

        client = LLMClient()
        table_preview = json.dumps(result_table[:20], default=str)
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Code that was run:\n{state.get('code', '')}\n\n"
            f"Result repr:\n{state.get('result_repr', '')}\n\n"
            f"Result table (rows):\n{table_preview}\n\n"
            "Write the final answer."
        )
        answer = client.call_model(prompt, system=_prompt("verify.md"))
        _log.info("node.verify", run_id=state.get("run_id"), verified=verified)
        return {
            **state,
            "answer_text": answer.strip(),
            "verified": verified,
            **_accumulate_tokens(state, client),
        }
    except Exception as exc:
        _log.error("node.verify.error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"verify failed: {exc}"}


def finalize(state: AgentState) -> AgentState:
    _log.info("node.finalize", run_id=state.get("run_id"), status="completed")
    return {**state, "status": "completed"}


def handle_error(state: AgentState) -> AgentState:
    _log.error(
        "node.handle_error",
        run_id=state.get("run_id"),
        error=state.get("error"),
    )
    return {**state, "status": "failed"}
