# Roadmap

---

## What This Agent Does

A personal, fully-local data-analysis agent. A single user uploads a data file (CSV in Phase 1; Excel and local DB tables later) and asks questions in plain English. The agent auto-profiles each dataset on load, then for each question plans a strategy, writes Python, runs it locally against the data, inspects the result, fixes-and-retries until the answer holds (bounded step limit), verifies its own numbers reconcile, and returns a written answer plus a summary table plus (where sensible) an auto-picked chart. Every question, the exact code run, and the result are persisted to a local PostgreSQL audit trail so results are reviewable and reproducible. Nothing leaves the machine — reasoning runs on a local Ollama model, analysis runs in-process via DuckDB and pandas.

## Who Uses It

A single technical-but-not-necessarily-coding individual (analyst, founder, researcher) doing decisions-grade personal analysis on their own data, on their own machine, who needs transparency and an audit trail rather than a black box, and who cannot let the data leave the device.

## Core Problem Being Solved

Replaces the manual loop of "open the file in pandas/Excel, write a query, eyeball it, doubt it, redo it" and the trust problem of cloud AI tools that exfiltrate data. Gives plain-English querying with a verified, audited, reproducible answer — locally.

## Success Criteria

- [ ] A user can upload a CSV and, within one screen, see an accurate profile (column names, types, row count, null/duplicate flags) generated from the real file.
- [ ] A user can ask a plain-English question and receive a written answer whose key numbers match a hand-computed check on the same CSV.
- [ ] The generated Python for every answer is viewable, and the same question on the same data yields the same answer (reproducible).
- [ ] Every question, its exact code, its result, and timing/token stats are retrievable from the PostgreSQL audit trail after the fact.
- [ ] No network call leaves localhost during analysis — the only LLM endpoint is `http://localhost:11434/v1` (Ollama).

## What This Agent Does NOT Do (Out of Scope)

- No cloud LLM, no telemetry, no data upload off-device — ever.
- No multi-user, no auth, no cloud deployment (single-user local desktop-style app).
- No write-back to source databases (read-only connections when DB tables arrive in Phase 3).
- No arbitrary shell/network access from generated code — execution is sandboxed to data analysis over the loaded datasets.
- No scheduled/automated runs — every analysis is user-triggered.

## Key Constraints

- **Fully local:** LLM = Ollama OpenAI-compatible endpoint (`AGENT_LLM_BASE_URL`, model `AGENT_LLM_MODEL`, no API key). Analysis = DuckDB + pandas in-process.
- **Correctness over speed:** bounded self-correcting retry loop with a verification step; a wrong answer is worse than a slow one.
- **Scale:** small files (few MB) up to millions of rows — DuckDB with sampling/streaming where full in-memory load is infeasible (Phase 3).
- **Trust bar:** personal but decisions-grade — audited, reproducible, transparent.
- **Platform:** Windows 11, Python via `uv`, frontend via `pnpm`, PostgreSQL local, port 8001.

> **Assumed:** app runs bound to `127.0.0.1` only (no external interface) to enforce the "nothing leaves the machine" constraint.
> **Assumed:** generated Python executes in an in-process restricted namespace (no `os`/`subprocess`/`socket`/`open` on arbitrary paths; datasets exposed as pre-loaded DataFrames / a DuckDB connection). This is a pragmatic guardrail for a single-user local tool, not a hardened sandbox.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Backend is minimal but REAL on the one core path; frontend is visually complete with clearly-labelled NON-FUNCTIONAL stubs for later phases.

### Phase 1 — Upload one CSV, ask one question, get a verified audited answer

- **Goal:** Upload ONE CSV → agent auto-profiles it → user asks ONE plain-English question → the LangGraph agent writes Python, runs it locally, verifies, and returns a written answer + key numbers + summary table + (where sensible) one auto-picked chart → generated code shown collapsibly → question/code/result persisted to the PostgreSQL audit trail.
- **Independent slices (parallel build units):**
  - `backend` (backend, deps: none) — replace the `transform_text` capability slot with the analysis graph: add the `ollama` LLM provider; LangGraph nodes `profile_dataset` → `plan` → `write_code` → `execute_code` → `inspect` (retry loop, bounded) → `verify` → `finalize` (+ `handle_error`); DuckDB/pandas execution engine with a restricted namespace; CSV upload + profile endpoint, ask endpoint, get-audit-record endpoint; PostgreSQL models + Alembic migration for `sessions`, `datasets`, `queries`; switch settings/session to `postgresql+psycopg`; structured request/response logging.
  - `frontend` (frontend, deps: API contract in `spec/api.md`) — replace `page.tsx`: upload panel, profile view, question box, answer + summary-table + chart render, collapsible generated-code view, plus clearly-labelled NON-FUNCTIONAL stubs (multi-dataset sidebar, DB-connect button, follow-up chips, streaming step-counter/timer, edit-and-rerun, Excel, CSV export); Playwright E2E smoke test.
- **Key surfaces / files:**
  - backend: `src/config/settings.py`, `src/db/session.py`, `src/db/models.py`, `alembic/versions/*`, `src/llm/providers/ollama.py`, `src/llm/client.py`, `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/analysis/` (new: DuckDB/pandas engine, profiler, charts), `src/prompts/*.md`, `src/api/datasets.py`, `src/api/ask.py`, `src/api/audit.py`, `src/domain/*`, `tests/`.
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/app/components/*`, `frontend/tests/e2e/`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest` (real Ollama at `AGENT_LLM_BASE_URL` + real PostgreSQL from `.env`), then `cd frontend; pnpm build; pnpm exec playwright test`.
- **How the user tests it (handoff seed):** Start PostgreSQL and Ollama (`ollama run qwen2.5-coder:7b` once to pull). Run `uv run alembic upgrade head`, then `uv run python -m src`. Build UI: `cd frontend; pnpm install; pnpm build`. Open `http://localhost:8001/app/`. Upload a CSV (e.g. a sales export). Confirm the profile shows correct column names/types/row count and null/dup flags. Type a question like "What is the total revenue by region?". Expect a written answer with numbers, a summary table, and a bar chart. Expand the code panel to see the exact Python. **Real:** upload, profile, ask, answer, table, chart, code view, audit persistence. **Labelled stubs (visible, non-functional):** multi-dataset sidebar, "Connect DB", follow-up suggestion chips, live step-counter/timer, edit-and-rerun, Excel upload, "Export CSV".

### Phase 2 — Multi-dataset analysis, live trace, follow-ups, and editable rerun

- **Goal:** Turn the single-dataset session into a real workbench: load several CSVs at once and ask questions that join/compare/union them (auto-picking relevant datasets), watch a live step trace with a "Step 3 of 6" counter and elapsed timer while the answer streams, get 2-3 suggested follow-up questions after each answer, and edit the generated code and rerun it.
- **Capabilities delivered:** `multi_dataset_analysis`, `streaming_step_trace`, `followup_suggestions`, `editable_rerun` (4).
- **Independent slices (parallel build units):**
  - `backend-multi` (backend, deps: none) — extend graph state + dataset registry to hold multiple datasets and derived tables; dataset-selection in `plan`; join/union support in the execution engine; register additional uploads under a session.
  - `backend-stream` (backend, deps: none — disjoint files) — SSE/streaming endpoint emitting per-step trace events (step index, total-estimate, elapsed, streamed answer tokens); `followup_suggestions` node; edit-and-rerun endpoint that executes user-supplied code in the same restricted namespace and records a new audit row.
  - `frontend` (frontend, deps: API contract) — wire the stubbed multi-dataset sidebar, follow-up chips, streaming step-counter/timer, and edit-and-rerun into real behavior.
- **Key surfaces / files:** backend-multi: `src/analysis/registry.py`, `src/graph/state.py`, `src/graph/nodes.py`, `src/api/datasets.py`. backend-stream: `src/api/ask.py` (stream), `src/api/rerun.py`, `src/graph/nodes.py` (followups — coordinate via distinct functions), `src/observability/events.py`. frontend: `frontend/src/app/components/*`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/phase2` (real Ollama + PostgreSQL), then `cd frontend; pnpm build; pnpm exec playwright test tests/e2e/phase2.spec.ts`.
- **How the user tests it:** Upload two related CSVs (e.g. orders + customers). Ask "average order value per customer segment" (requires a join). Watch the step counter/timer advance and the answer stream in. Click a suggested follow-up. Expand the code, edit a line, rerun, and see the updated answer plus a new audit row.

### Phase 3 — DB tables, Excel, big-data sampling, CSV export, cross-day resume

- **Goal:** Make it a durable local workbench for real-sized data: connect read-only to a local database table, ingest Excel workbooks, handle millions-of-rows via DuckDB sampling/streaming, download derived datasets/chart data as CSV, and resume a saved session (datasets + history) across days.
- **Capabilities delivered:** `db_table_connection`, `excel_ingestion`, `large_data_sampling`, `csv_export`, `session_resume` (5).
- **Independent slices (parallel build units):**
  - `backend-sources` (backend, deps: none) — read-only DB-table connector + Excel loader in the ingestion layer; both flow through the existing profiler.
  - `backend-scale` (backend, deps: none — disjoint files) — DuckDB out-of-core / sampling path for datasets above an in-memory threshold, with the sample vs full-scan choice recorded per query; CSV export endpoint for derived tables and chart data.
  - `backend-resume` (backend, deps: none — disjoint files) — session list/load endpoints that rehydrate datasets and conversation history from PostgreSQL + on-disk dataset store.
  - `frontend` (frontend, deps: API contract) — wire the stubbed Connect-DB, Excel upload, Export-CSV, and a session-picker for resume.
- **Key surfaces / files:** backend-sources: `src/analysis/ingest.py`, `src/api/datasets.py`. backend-scale: `src/analysis/engine.py`, `src/api/export.py`. backend-resume: `src/api/sessions.py`, `src/analysis/registry.py`. frontend: `frontend/src/app/components/*`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/phase3` (real Ollama + PostgreSQL; large-data test uses a ≥2,000,000-row fixture so a sampled answer and a full-scan answer are observably different), then `cd frontend; pnpm build; pnpm exec playwright test tests/e2e/phase3.spec.ts`.
- **How the user tests it:** Connect a local PostgreSQL table, ingest an `.xlsx`, ask a question over a multi-million-row CSV (observe the sampling note), export a derived result as CSV, close the app, reopen next day, pick the prior session, and confirm datasets and history are restored.
