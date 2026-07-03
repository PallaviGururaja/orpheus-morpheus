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

> **Shipped since Phase 1 handoff (current reality — do not revert):** the upload `<input>` no longer has a CSV-only `accept` filter and the sidebar "Add dataset" is wired; `src/analysis/executor.py` coerces NaN/Inf (Python and numpy floats) to `None` before JSONB persistence; a NEW in-app file browser is now the **primary** upload path — backend `src/api/local_files.py` (`GET /local/browse`, `POST /datasets/local`, home-confined) plus frontend `FileBrowser.tsx` modal ("Browse my computer"). `src/api/local_files.py` currently has **no tests** — that debt is cleared in the `backend-multi` slice below.

- **Goal:** Turn the single-dataset session into a real workbench: load several CSVs at once and ask questions that join/compare/union them (with automatic dataset selection when the question implies specific datasets), watch a live step trace with a "Step 3 of 6" counter and elapsed timer while the answer streams, get 2-3 suggested follow-up questions after each answer, and edit the generated code and rerun it.
- **Capabilities delivered:** `multi_dataset_analysis`, `streaming_step_trace`, `followup_suggestions`, `editable_rerun` (4).
- **Independent slices (parallel build units — disjoint file ownership):**
  - `backend-multi` (backend, deps: none) — make `/ask` actually use every id in `dataset_ids`: register each dataset as a named DuckDB table + expose each as a named DataFrame in the restricted namespace so generated code can JOIN/COMPARE/UNION across them; `plan` loads **all** in-scope dataset profiles from the DB (keyed by table name) and picks the relevant datasets when the question implies specific ones; the execution engine gains multi-table registration. **Also clears the `local_files.py` test debt** (this slice owns the dataset/upload surface): browse lists CSVs, load-by-path works, a path outside home is rejected 403, a non-CSV path is rejected 400.
  - `backend-stream` (backend, deps: none — disjoint files) — `GET /ask/stream` (SSE) emitting per-step trace events (step index, total estimate, elapsed) and the streamed answer, built by wrapping the LangGraph run at the **runner** level (no edits to `nodes.py`); `GET /queries/{id}/followups` calling a standalone `generate_followups` helper; `POST /queries/{id}/rerun` executing user-edited Python in the same restricted namespace and recording a NEW audit row (`is_rerun=true`). **Folds in the stuck-lock robustness fix** (see below) since it owns the ask-flow concurrency code.
  - `frontend` (frontend, deps: API contract in `spec/api.md` only) — turn the labelled stubs real: multi-dataset sidebar that lists all loaded datasets with a remove control; replace the disabled "Live step trace & elapsed timer" badge and the static "Analyzing locally…" spinner with a real "Step 3 of 6" counter + elapsed timer fed by `GET /ask/stream`; render `GET /queries/{id}/followups` as clickable chips in `AnswerBlock`'s follow-up area; make `CodePanel` editable with a Rerun button showing the new result.
- **Robustness bug folded into `backend-stream`:** when an `/ask` run's client disconnects mid-run (browser refresh/close/dropped connection), the query is currently left `status="pending"` forever and the per-session concurrency lock (`_running_sessions` in `src/api/ask.py`) is never released, so every subsequent `/ask` returns **409 CONFLICT** and the session is permanently blocked. Fix: an abandoned/disconnected run must be marked `failed` and release the lock — mark pending runs `failed` on timeout and/or preempt a stale lock on a new request and/or make the lock reclaimable. Add a test that simulates a disconnect/abandonment and asserts the next `/ask` succeeds (no permanent 409).
- **Key surfaces / files:**
  - `backend-multi`: `src/analysis/executor.py` (multi-table registration — `execute_python` gains a `tables: dict[str, DataFrame]` form), `src/analysis/engine.py` (load helpers), `src/graph/nodes.py` (`_load_dataframes`, `execute_code`, `plan` dataset-selection + all-profile load), `src/graph/state.py`, `tests/phase2/test_local_files.py` (NEW — the local_files.py coverage).
  - `backend-stream`: `src/api/ask.py` (stream endpoint + lock fix), `src/api/rerun.py` (NEW), `src/api/followups.py` (NEW), `src/graph/followups.py` (NEW — standalone `generate_followups`), `src/graph/runner.py` (streaming generator wrapping `agentic_ai.stream(...)`), `src/observability/events.py` (event schema), `src/prompts/followups.md`.
  - `frontend`: `frontend/src/app/components/{Sidebar,AnswerBlock,CodePanel}.tsx`, `frontend/src/app/lib/{api,types}.ts`, `frontend/src/app/page.tsx`, `frontend/tests/e2e/phase2.spec.ts`.
  - **Coordination note:** `nodes.py` is owned by `backend-multi` **only**; `runner.py` by `backend-stream` **only**. They stay disjoint by design — multi-dataset profile assembly lives entirely inside the graph nodes (loading from the DB by `dataset_ids`), so `runner.py` needs no multi-dataset change, and streaming is a runner-level wrapper needing no node change. The frontend depends on the API contract only, not on backend internals.
- **Gate commands (run per slice, real Ollama + PostgreSQL from `.env`):**
  - `backend-multi`: `uv run alembic upgrade head && uv run pytest tests/phase2/test_multi_dataset.py tests/phase2/test_local_files.py -q` — the join test uses two related CSVs whose correct answer requires the join (a single-table answer is observably wrong).
  - `backend-stream`: `uv run pytest tests/phase2/test_stream.py tests/phase2/test_rerun.py tests/phase2/test_followups.py tests/phase2/test_lock_reclaim.py -q`
  - `frontend`: `cd frontend; pnpm build; pnpm exec playwright test tests/e2e/phase2.spec.ts`
- **How the user tests it (handoff seed):** Open `http://localhost:8001/app/`. Click **"Browse my computer"** (the primary upload — the in-app `FileBrowser` modal, home-confined) and pick a first CSV (e.g. `orders.csv`); then use the sidebar to add a second related CSV (e.g. `customers.csv`) — both now appear in the multi-dataset sidebar, each with a remove (×) control. Ask a question that needs the join, e.g. "average order value per customer segment". Watch the spinner replaced by a live **"Step 3 of 6"** counter and an elapsed timer while the answer streams in. Confirm the answer reflects the join across both files (not one file alone). Under the answer, click one of the real suggested follow-up chips and see it run. Expand the code panel, edit a line, click **Rerun**, and see the updated result plus a new audit row in history. To confirm the lock fix: start a run, refresh the browser mid-run, then ask again — it must succeed (no permanent 409). **Real:** browse-and-load, multi-dataset sidebar + remove, join analysis, streaming step counter/timer, follow-up chips, edit-and-rerun. **Still labelled stubs (Phase 3):** Connect DB, Upload Excel, Export CSV, Switch session.

### Phase 3 — Drag-and-drop dashboard builder (headline), CSV export, Excel, session resume, DB connect

> **Current-reality preamble (do not revert):** the reasoning LLM is now **cloud Gemini** per `.env` (`AGENT_LLM_PROVIDER=gemini`, `AGENT_LLM_MODEL=gemini-2.5-flash`) — this laptop has no GPU, and `.env` is the source of truth. Earlier phases' wording about Ollama/fully-local reasoning is left as historical; **Phase 3 does not re-assert the Ollama-only constraint.** The Phase 3 headline (dashboard aggregation) and the CSV exports are **deterministic and use NO LLM at all** — they run in-process via pandas/DuckDB over already-loaded datasets. `fast_mode` (`settings.fast_mode`) remains honored where the LLM is used; raw data rows never go to the LLM — only schema, generated code, and aggregated results.

- **Goal:** Turn the answer-oriented workbench into a **composable dashboard**: the user drags dataset columns onto a canvas to build multiple aggregated charts (bar/line/scatter/pie/table) with no typing, names and saves the dashboard, and reloads it later — plus the un-stubbing of CSV export, Excel ingestion, cross-day session resume, and (lowest priority) read-only local DB-table connect.
- **Capabilities delivered:** `dashboard_builder` (headline), `csv_export`, `excel_ingestion`, `session_resume`, `db_table_connection` (5). (Large-data sampling is deferred to Phase 4 — see index.)
- **Independent slices (parallel build units — DISJOINT file ownership):**

  - **`dashboard-backend`** (backend, deps: none) — **THE HEADLINE.** Deterministic aggregation endpoint `POST /dashboard/aggregate` `{dataset_id, dimensions:[col…], measure:col|null, agg:'sum'|'avg'|'count'|'min'|'max', chart_type:'bar'|'line'|'scatter'|'pie'|'table'}` → aggregated rows computed in-process via pandas/DuckDB (reuses `src/analysis`), validating that every column exists in the dataset profile, capping output rows, and handling the no-measure `count` case. **NO LLM.** PLUS dashboard persistence: new `dashboard` table (`id`, `session_id`, `name`, `widgets` JSONB, `created_at`) and CRUD endpoints `POST /dashboards`, `GET /dashboards`, `GET/PUT/DELETE /dashboards/{id}`. New Alembic migration on head `dfeac34fb4f1` (do not edit existing migrations).
    - **Owns:** `src/api/dashboard.py` (NEW), `src/analysis/aggregate.py` (NEW deterministic aggregation helper — must NOT collide with `src/analysis/executor.py`), `src/db/models.py` (append `Dashboard` model only), `alembic/versions/<new>_add_dashboard.py` (NEW), `tests/phase3/test_dashboard.py` (NEW).
    - **Gate:** `uv run alembic upgrade head && uv run pytest tests/phase3/test_dashboard.py -q` (real PostgreSQL from `.env`).

  - **`dashboard-frontend`** (frontend, deps: `dashboard-backend` API contract only) — a **"Dashboard"** tab/toggle alongside **"Ask"**. A palette of draggable **column chips** derived from the active dataset's profile (string / low-cardinality → dimension chips; numeric → measure chips). A canvas of **widgets**, each with drop zones (dimensions + one measure), an aggregation selector, and a chart-type selector; on a valid drop it calls `POST /dashboard/aggregate` and renders through the existing `recharts` `ChartView` (extended to add **pie** and **table** rendering). Widgets can be added / removed / rearranged in a grid, and the whole dashboard can be named, saved, and reloaded (`/dashboards`). Drag-and-drop via native HTML5 DnD or a DnD lib added with `corepack pnpm add` (must stay self-contained in the static export). Clean, EBCO-branded. **Owns the `page.tsx` Ask/Dashboard tab toggle + dashboard mount** (coordination point — see note).
    - **Owns:** `frontend/src/app/components/dashboard/*` (NEW — Palette, Canvas, Widget, DropZone, controls), `frontend/src/app/components/ChartView.tsx` (extend for pie/table), the tab-toggle + dashboard mount in `frontend/src/app/page.tsx`, `frontend/tests/e2e/phase3-dashboard.spec.ts` (NEW).
    - **Gate:** `cd frontend; corepack pnpm build; corepack pnpm exec playwright test tests/e2e/phase3-dashboard.spec.ts`.

  - **`export`** (backend + frontend, deps: none for backend; frontend depends on `GET /queries/{id}/export` contract) — wire `GET /queries/{id}/export` → download a persisted query's `result_table` as CSV; turn the currently-stubbed **Export** button on `AnswerBlock` real. Also export a single dashboard widget's aggregated data as CSV (`GET /dashboards/{id}/widgets/{widget_id}/export` or client-side blob from the widget's already-fetched rows — see api.md).
    - **Owns:** `src/api/export.py` (NEW — both the query-export and the widget-export endpoints), `frontend/src/app/components/AnswerBlock.tsx` (the answer Export button only), `tests/phase3/test_export.py` (NEW).
    - **Coordination:** to avoid a `dashboard/Widget.tsx` collision, the **frontend widget-export button lives in `dashboard-frontend`** (it already holds the widget's fetched rows and serializes them client-side, or calls the export endpoint) — `export` owns only the backend `src/api/export.py` and the Ask-tab `AnswerBlock.tsx` button. `export`'s only frontend file is `AnswerBlock.tsx`; it does NOT touch the `dashboard/` dir.
    - **Gate:** `uv run pytest tests/phase3/test_export.py -q` (real PostgreSQL from `.env`).

  - **`excel`** (backend + frontend, deps: none) — accept `.xlsx` in both the multipart upload and the in-app file browser (`openpyxl` is already a dependency); load the first sheet (or let the user pick a sheet); remove the "Upload Excel" stub.
    - **Owns:** `src/analysis/ingest.py` (Excel branch of the loader used by `datasets`/`local_files`), `tests/phase3/test_excel.py` (NEW), `frontend/src/app/components/UploadPanel.tsx` (the `<input>` `accept` + the `.csv$`-only guard at line ~38 → allow `.xlsx`) and `frontend/src/app/components/FileBrowser.tsx` (`.xlsx` listing/selection). Both are disjoint from `page.tsx` (owned by `dashboard-frontend`).
    - **Coordination:** the Excel branch lives entirely in the shared **loader function** (`src/analysis/ingest.py`); `excel` does NOT edit `src/api/local_files.py` (it only extends the file-extension allow-list the loader enforces). If a route-level `.xlsx` allow must change in `local_files.py`, that one-line allow-list change is made by `excel` and flagged in the PR — no other slice touches that file this phase.
    - **Gate:** `uv run pytest tests/phase3/test_excel.py -q`.

  - **`session-resume`** (backend + frontend, deps: none) — `GET /sessions` already lists sessions; add load/rehydrate of a prior session with its datasets + query history, and replace the "Switch session" stub with a **session picker**.
    - **Owns:** `src/api/sessions.py` (list + load/rehydrate), `frontend/src/app/components/SessionPicker.tsx` (NEW) mounted from `Sidebar.tsx`, `tests/phase3/test_session_resume.py` (NEW).
    - **Coordination:** the session picker mounts inside `Sidebar.tsx` (owned here for the "Switch session" control), not in `page.tsx`.
    - **Gate:** `uv run pytest tests/phase3/test_session_resume.py -q` (real PostgreSQL from `.env`).

  - **`db-connect`** (backend + frontend, deps: none — **LOWEST priority**) — read-only connect to a local PostgreSQL/SQLite and load a table as a dataset; replace the "Connect DB" stub with a modal. If it proves too large within the phase budget, **ship it as a clearly-labelled stub deferred to Phase 4** (never a broken control).
    - **Owns:** `src/api/db_connect.py` (NEW), `frontend/src/app/components/ConnectDbModal.tsx` (NEW) mounted from `Sidebar.tsx`, `tests/phase3/test_db_connect.py` (NEW).
    - **Coordination:** mounts inside `Sidebar.tsx` alongside (but disjoint from) the session picker — separate components, no shared control.
    - **Gate:** `uv run pytest tests/phase3/test_db_connect.py -q` (real PostgreSQL from `.env`).

- **Shared-file coordination (call-outs):**
  - `page.tsx` — **only `dashboard-frontend`** edits it (adds the Ask/Dashboard tab toggle + dashboard mount). All other frontend slices edit their OWN components (`AnswerBlock`, `FileBrowser`, `Sidebar`, new modals) so they never collide in `page.tsx`.
  - `src/db/models.py` — **only `dashboard-backend`** appends the `Dashboard` model this phase.
  - Alembic — **only `dashboard-backend`** adds a migration (single new head on `dfeac34fb4f1`); no other slice creates a migration.
  - `src/analysis/` — `dashboard-backend` owns the NEW `aggregate.py`; `excel` owns `ingest.py`; disjoint files, no collision with `executor.py`.
  - `Sidebar.tsx` — both `session-resume` (mounts `SessionPicker`) and `db-connect` (mounts `ConnectDbModal`) add a mount line here. They append to **disjoint regions** (session controls vs data-source controls) with distinct new components. If concurrency risks a merge conflict, `db-connect` (lower priority, and possibly deferred) **serializes after `session-resume`** for this one file — it is the only true frontend-shared-file dependency this phase.
  - `spec/api.md` / `spec/ui.md` — documentation touched here by spec-writer; generators read, do not rewrite.
  - **Priority order if cutting scope:** cut `db-connect` first, then `session-resume`. `dashboard-backend` + `dashboard-frontend` (the headline) and `export` are the non-negotiable core.

- **Priority / scheduling:** `dashboard-backend`, `export`, `excel`, `session-resume`, `db-connect` fan out concurrently (all deps: none). `dashboard-frontend` starts against the `dashboard-backend` API contract in `spec/api.md` and can build UI in parallel, integrating once the aggregate endpoint is live.
- **Gate command (whole phase):** `uv run alembic upgrade head && uv run pytest tests/phase3 -q` (real PostgreSQL from `.env`; the dashboard aggregation test asserts pandas/DuckDB group-by results match a hand-computed aggregate over a fixture with several dimension groups so a wrong grouping is observably wrong), then `cd frontend; corepack pnpm build; corepack pnpm exec playwright test tests/e2e/phase3-dashboard.spec.ts`.
- **How the user tests it (handoff seed):** Open `http://localhost:8001/app/`, load a dataset, then click the new **Dashboard** tab. Drag a string column (e.g. `region`) into a widget's dimension zone and a numeric column (e.g. `revenue`) into its measure zone, pick `sum` and `bar` — the bar chart renders instantly (no typing, no LLM). Add a second widget as a `pie` of `count` by `category`, and a third as a `table`. Rearrange them, name the dashboard "Sales overview", click Save, reload the page, reopen it from the dashboard list, and confirm it restores. On the Ask tab, click the now-real **Export** button under an answer to download its table as CSV. Load an `.xlsx` via "Browse my computer". Use the session picker to reopen a prior session with its datasets + history. **Real:** the dashboard builder end-to-end (drag → aggregate → chart, save/reload), CSV export, Excel ingestion, session resume. **Labelled stub (if cut):** "Connect DB" may remain a clearly-labelled Phase-4 stub.
