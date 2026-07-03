# UI

---

## UI Type

Desktop-style local **web app** — Next.js 15 static export (React 19), served at `http://localhost:8001/app/`. Single-page workbench. Charts via `recharts`.

## Views / Screens

### Screen: Workbench (single page)

**Purpose:** Load a dataset, ask questions, read verified answers with tables/charts, inspect the generated code, and review history.

**Layout regions:**

- **Left sidebar — Datasets & Sessions**
  - **Real (Phase 1):** the currently loaded dataset with name, row count, column count.
  - **Labelled stub:** "Add dataset" (multi-dataset), "Connect DB", and a session-switcher — all rendered greyed with a "Coming soon" tag so they read as roadmap, not bugs.

- **Center — Conversation**
  - **Upload panel (real):** drag/drop or pick a CSV → `POST /datasets`; on success shows the **profile card** (columns + types, row count, null/dup/outlier flags).
  - **Question box (real):** text input → `POST /ask`.
  - **Answer block (real):** written answer text, a **summary table**, and (where sensible) an auto-picked **chart** (bar/line/scatter from `chart_spec`).
  - **Collapsible code panel (real, read-only in Phase 1):** the exact generated Python; an "Edit & rerun" button is present but **labelled stub**.
  - **Labelled stubs:** follow-up suggestion chips under each answer; a "Step 3 of 6" counter + elapsed timer + streaming text (Phase 1 shows a simple spinner instead, with the step-counter UI visibly disabled/"soon").

- **Right panel — Audit / History (real, read-only)**
  - List of prior questions for the session (`GET /sessions/{id}/queries`); clicking one loads its full record (question, code, result, tokens, elapsed) via `GET /queries/{id}`.

**Actions available (Phase 1, real):** upload CSV, view profile, ask a question, read answer + table + chart, expand code, browse history. **Stubbed (labelled):** add/join datasets, connect DB, edit-and-rerun, follow-up chips, streaming step/timer, Excel, export CSV.

## Error States

- **Loading:** upload and ask show inline spinners; the ask spinner notes "Analyzing locally…".
- **Ollama down (503):** banner "Local model unavailable — is Ollama running?" with the failed question preserved.
- **Bad file (400):** inline error on the upload panel.
- **Analysis failed (500):** the answer block shows the error plus, when available, the last code the agent tried and the execution error (transparency — "show where it got stuck").
- **Stub clicked:** a small "Coming in a later phase" toast — never a broken state.

## Tech Stack

Next.js 15 static export + React 19 + Tailwind (boilerplate) + `recharts` for charts. Built with `pnpm build`; served from `/app/`. E2E via `@playwright/test` in `frontend/tests/e2e/`.
