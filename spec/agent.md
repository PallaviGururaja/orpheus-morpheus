# Agent

---

## Agent Architecture Pattern

**Chosen: Graph (LangGraph).** The analysis is a multi-step pipeline with a bounded self-correcting loop (write code → execute → inspect → retry) and a conditional verify/finalize path — exactly what conditional edges + a step counter in state express cleanly. A single deterministic tool-loop cannot express the "inspect failed → rewrite → re-execute up to N times, then verify" routing.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `plan` | Ollama (local) | `qwen2.5-coder:7b` | Local, code-capable; plans a short analysis strategy |
| `write_code` | Ollama (local) | `qwen2.5-coder:7b` | Code model generates the pandas/DuckDB Python |
| `inspect` (fix decision) | Ollama (local) | `qwen2.5-coder:7b` | Reads the error/result and decides fix vs done |
| `verify` | Ollama (local) | `qwen2.5-coder:7b` | Composes the written answer and reconciles numbers |
| `followup_suggestions` (Phase 2) | Ollama (local) | `qwen2.5-coder:7b` | Proposes 2-3 follow-up questions |

All nodes use the single local model via `AGENT_LLM_MODEL`; no per-node model switching (one local model is available). Model is env-configurable via `AGENT_LLM_MODEL`.

**Fallback behaviour:** If Ollama is unreachable, the LLM call raises; the current node catches it, sets `state["error"]`, and routes to `handle_error`, which persists a failed `queries` row and returns a 503-style message ("local model unavailable"). No cloud fallback — this is a local-only tool. Tests call the real local Ollama from `.env`.

**Prompt strategy:** System/user split. System prompts live in `src/prompts/` (`plan.md`, `write_code.md`, `verify.md`, `followups.md`). `write_code` is given the dataset profile + available variable names (pre-loaded DataFrame(s) / DuckDB connection) and must emit a single Python block that assigns `result`. Structured expectations are enforced by parsing a fenced code block, not JSON mode (Ollama models are unreliable at strict JSON).

---

## Tools & Tool Calling

The agent does not use LLM-driven tool selection; nodes call the analysis engine directly (rule-based routing). The "tool" is the code executor.

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `execute_python` | Runs generated code in a restricted namespace with datasets pre-bound | `code: str`, dataset handles | `result` value + captured stdout/error + repr | None outside the namespace (no fs/net) |
| `profile_dataframe` | Computes columns, dtypes, ranges, row count, null/dup/outlier flags | DataFrame | profile dict | None |
| `select_chart` | Picks bar/line/scatter (or none) from the result shape | result table | chart spec | None |

**Tool selection strategy:** forced/deterministic — `execute_code` always runs `execute_python`; profiling and chart selection are called by their respective nodes.

**Tool failure handling:** `execute_python` never raises to the graph — it returns the error text, which `inspect` reads to decide a retry. Retries are bounded by `max_steps`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                       # queries.id, set at initialisation
    session_id: str                   # owning session
    dataset_ids: list[str]            # datasets in scope (one in Phase 1)

    # Input
    question: str                     # the user's plain-English question
    profile: dict                     # dataset profile(s), from profile_dataset
    messages: list                    # prior chat turns (session memory)

    # Pipeline data (populated progressively)
    plan: str                         # short strategy text from `plan`
    code: str                         # latest generated Python
    exec_stdout: str                  # captured stdout
    exec_error: str | None            # execution error text (None if clean)
    result_repr: str                  # repr/preview of `result`
    result_table: list[dict]          # summary table rows
    step: int                         # current step index (1-based)
    max_steps: int                    # bounded retry limit (default 6)

    # Output
    answer_text: str                  # written answer from `verify`
    chart_spec: dict | None           # {type, x, y, series} or None
    verified: bool                    # did numbers reconcile
    followups: list[str]              # Phase 2

    # Control
    error: str | None                 # fatal failure (set by any node)
    status: str                       # pending|completed|failed
```

---

## Nodes / Steps

### `profile_dataset`
**Reads:** `dataset_ids`. **Writes:** `profile`.
**LLM call:** no. **External:** analysis engine (`profile_dataframe`). Loads each dataset and computes the profile. (In Phase 1 called once at upload time and cached on the `datasets` row; the ask-graph reads the cached profile, so this node reads from DB rather than recomputing.)

### `plan`
**Reads:** `question`, `profile`, `messages`. **Writes:** `plan`, `step=1`.
**LLM call:** yes (`plan.md`). Produces a short strategy (which columns, what aggregation, any join). On LLM failure: set `error` → `handle_error`.

### `write_code`
**Reads:** `plan`, `profile`, `code`, `exec_error`. **Writes:** `code`.
**LLM call:** yes (`write_code.md`). On a retry, the prior `code` + `exec_error` are included so the model fixes the failure. Emits a single fenced Python block assigning `result`.

### `execute_code`
**Reads:** `code`, `dataset_ids`. **Writes:** `exec_stdout`, `exec_error`, `result_repr`, `result_table`, `chart_spec`, increments `step`.
**LLM call:** no. **External:** `execute_python` (restricted namespace, datasets pre-bound). Never raises — captures errors into `exec_error`.

### `inspect`
**Reads:** `exec_error`, `result_repr`, `step`, `max_steps`. **Writes:** routing only (no LLM needed for the pure-error case; for ambiguous-but-clean results a light LLM check decides "good enough").
**Behaviour:** if `exec_error` and `step < max_steps` → back to `write_code`; if `exec_error` and `step >= max_steps` → `handle_error`; if clean → `verify`.

### `verify`
**Reads:** `question`, `result_repr`, `result_table`, `code`. **Writes:** `answer_text`, `verified`, refines `chart_spec`.
**LLM call:** yes (`verify.md`). Composes the written answer AND reconciles headline numbers against the result (e.g. sums/row counts). If reconciliation fails and `step < max_steps`, routes back to `write_code`; else finalizes with `verified=False` and a flagged assumption.

### `followup_suggestions` (Phase 2)
**Reads:** `question`, `answer_text`, `profile`. **Writes:** `followups`.
**LLM call:** yes (`followups.md`). Non-fatal — on failure logs and continues with empty `followups`.

### `finalize`
**Reads:** all output fields. **Writes:** `status="completed"`. Persists the final `queries` audit row (question, final code, result, chart, tokens, elapsed).

### `handle_error`
**Reads:** `error`, `run_id`. **Writes:** `status="failed"`. Persists a failed `queries` row with `error_message`, logs with `run_id`.

---

## Graph / Flow Topology

```
START
  │
  ▼
plan ──(error)──► handle_error ──► END
  │
  ▼
write_code ──(error)──► handle_error
  │
  ▼
execute_code
  │
  ▼
inspect ──(exec_error & step<max)──► write_code
  │      └─(exec_error & step>=max)──► handle_error
  │ (clean)
  ▼
verify ──(not reconciled & step<max)──► write_code
  │ (reconciled OR step>=max)
  ▼
finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `plan` | `state.error` set | `handle_error` |
| `plan` | else | `write_code` |
| `write_code` | `state.error` set | `handle_error` |
| `write_code` | else | `execute_code` |
| `inspect` | `exec_error` and `step < max_steps` | `write_code` |
| `inspect` | `exec_error` and `step >= max_steps` | `handle_error` |
| `inspect` | no `exec_error` | `verify` |
| `verify` | not `verified` and `step < max_steps` | `write_code` |
| `verify` | else | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state | All in-progress data (plan, code, results, step) |
| **Across runs** | PostgreSQL | Sessions, datasets, full query/code/result audit trail |
| **Conversation** | `messages` in state, loaded from `queries` history for the session | Prior question/answer turns so follow-ups have context |

**Context window management:** prior turns are passed as a bounded sliding window (last K question/answer pairs); the dataset profile (not the raw data) is always in-prompt. Raw data never enters the prompt — the model writes code that operates on it.

> **Assumed:** conversation memory (session turn history) is a Phase 1 capability — the ask-graph loads the session's prior turns into `messages`. Even in Phase 1 (single dataset) a user asks multiple follow-up questions in one session, so turn memory is required, not deferred.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | What is shown | Expected user action | Timeout / default |
|------------|--------------|----------------------|-------------------|
| Clarifying question (on ambiguity) | The agent's clarifying question + best-guess assumption | User answers or accepts the best guess | No timeout — best-guess answer is still returned with the assumption flagged |
| Edit-and-rerun (Phase 2) | The generated code, editable | User edits + reruns | Optional — original answer stands if not used |

Phase 1 does not pause the graph; on ambiguity it returns a best-guess answer with a flagged assumption and (optionally) a clarifying question in the answer, rather than blocking.

---

## Error Handling & Recovery

**Node-level:** each LLM/engine-calling node wraps its work in try/except; fatal errors set `state["error"]` and route to `handle_error`. Execution errors are NOT fatal — they flow into `inspect` for a bounded retry.

**Graph-level (`handle_error`):** reads `error`, `run_id`; updates the `queries` row → `status="failed"`, `error_message`, `completed_at`; logs with `run_id`; terminates.

**Resume / retry strategy:** the write→execute→inspect loop is the retry mechanism (bounded by `max_steps`, default 6). A failed run is not auto-resumed; the user can ask again or (Phase 2) edit the code and rerun.

**Partial failure:** `followup_suggestions` (Phase 2) and chart selection are non-critical — on failure the agent returns the answer without follow-ups/chart rather than aborting.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One trace per run, one log event per node (step index, elapsed) | Structured stdout log (`src/observability/events.py`) |
| **LLM calls** | Prompt/completion tokens (from Ollama response usage), latency, model | Structured log + persisted per-query token/elapsed totals |
| **Code exec** | Generated code, stdout, error, success | Persisted on the `queries` row + structured log |
| **Run outcome** | Status, total duration, error if any | PostgreSQL `queries` row + structured log |

Observability is wired in Phase 1 (structured request/response + per-node logging). LangSmith is optional and off by default (local-only, no cloud) — the structured local log is the source of truth.

---

## Concurrency Model

- **Run isolation:** one analysis run at a time per session; each run is `run_id`-scoped. Single-user tool — a second concurrent `POST /ask` for the same session returns 409; different sessions may proceed independently.
- **Parallel nodes within a run:** none — the pipeline is sequential by nature (each step depends on the prior).
- **Checkpointing:** none in Phase 1 (runs are short). Phase 2 streaming uses in-memory event emission, not a persisted checkpointer.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("plan", plan)
graph.add_node("write_code", write_code)
graph.add_node("execute_code", execute_code)
graph.add_node("inspect", inspect)
graph.add_node("verify", verify)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("plan")

graph.add_conditional_edges(
    "plan",
    lambda s: "handle_error" if s.get("error") else "write_code",
)
graph.add_conditional_edges(
    "write_code",
    lambda s: "handle_error" if s.get("error") else "execute_code",
)
graph.add_edge("execute_code", "inspect")
graph.add_conditional_edges(
    "inspect",
    lambda s: (
        "verify" if not s.get("exec_error")
        else "write_code" if s["step"] < s["max_steps"]
        else "handle_error"
    ),
)
graph.add_conditional_edges(
    "verify",
    lambda s: "write_code" if (not s.get("verified") and s["step"] < s["max_steps"]) else "finalize",
)
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```
