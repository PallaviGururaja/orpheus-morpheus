# UI

---

## UI Type

Desktop-style local **web app** — Next.js 15 static export (React 19), served at `http://localhost:8001/app/`. Single-page workbench. Charts via `recharts`.

## Views / Screens

### Screen: Workbench (single page)

**Purpose:** Load a dataset, ask questions, read verified answers with tables/charts, inspect the generated code, and review history.

**Layout regions:**

- **Left sidebar — Datasets & Sessions**
  - **Real (Phase 2):** a list of **all** datasets loaded in the session (name, row count, column count), each with a **remove (×)** control. "Add dataset" opens the primary upload path — the `FileBrowser` "Browse my computer" modal (see below) — and adds another dataset to the same session.
  - **Labelled stub (Phase 3):** "Connect DB", "Upload Excel", and "Switch session" — rendered greyed with a "Coming soon" tag so they read as roadmap, not bugs.

- **FileBrowser modal — primary upload (real, `FileBrowser.tsx`)**
  - "Browse my computer" opens an in-app, home-confined file browser (`GET /local/browse`) with shortcuts (Home/Downloads/Documents/Desktop), an "↑ Up" control, folder navigation, and CSV files. Picking a file loads it via `POST /datasets/local`. This is the primary upload path (a reliable alternative to the OS dialog on Windows). Drag/drop multipart `POST /datasets` remains as a fallback.

- **Center — Conversation**
  - **Upload panel (real):** "Browse my computer" (primary) / drag-drop fallback; on success shows the **profile card** (columns + types, row count, null/dup/outlier flags).
  - **Question box (real):** text input → streams via `GET /ask/stream`.
  - **Live progress (real, Phase 2):** while a run is streaming, a **"Step 3 of 6" counter + elapsed timer** (fed by `step` SSE events) and the streaming answer text replace the old static "Analyzing locally…" spinner and the disabled "Live step trace" badge.
  - **Answer block (real):** written answer text, a **summary table**, and (where sensible) an auto-picked **chart** (bar/line/scatter from `chart_spec`).
  - **Follow-up chips (real, Phase 2):** 2-3 clickable suggested questions under each answer (`GET /queries/{id}/followups`); clicking one asks it.
  - **Collapsible code panel (real, editable, Phase 2):** the exact generated Python; now **editable** with a **Rerun** button (`POST /queries/{id}/rerun`) that runs the edited code and shows the new result (a new audit row).

- **Right panel — Audit / History (real, read-only)**
  - List of prior questions for the session (`GET /sessions/{id}/queries`); clicking one loads its full record (question, code, result, tokens, elapsed) via `GET /queries/{id}`. Rerun rows appear as new entries.

**Actions available (Phase 2, real):** browse-and-load CSV(s), manage multiple datasets (add/remove), view profile, ask a question, watch the live step counter/timer + streaming answer, read answer + table + chart, click follow-up chips, edit code and rerun, browse history. **Stubbed (labelled, Phase 3):** connect DB, upload Excel, export CSV, switch session.

## Error States

- **Loading:** upload shows an inline spinner; asking shows the live **step counter + elapsed timer** (no longer a bare "Analyzing locally…" spinner).
- **Stream interrupted (disconnect):** if the browser is refreshed/closed mid-run the run is abandoned server-side and the lock released; the next question starts cleanly (no permanent 409 blocked state).
- **Ollama down (503):** banner "Local model unavailable — is Ollama running?" with the failed question preserved.
- **Bad file (400):** inline error on the upload panel.
- **Analysis failed (500):** the answer block shows the error plus, when available, the last code the agent tried and the execution error (transparency — "show where it got stuck").
- **Rerun error (400):** the edited code's sandbox error is shown inline under the code panel so the user can fix and rerun.
- **Stub clicked (Phase 3 items only):** a small "Coming in a later phase" toast — never a broken state.

## Tech Stack

Next.js 15 static export + React 19 + Tailwind (boilerplate) + `recharts` for charts. Built with `pnpm build`; served from `/app/`. E2E via `@playwright/test` in `frontend/tests/e2e/`.
