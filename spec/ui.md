# UI

---

## UI Type

Desktop-style local **web app** — Next.js 15 static export (React 19), served at `http://localhost:8001/app/`. Single-page workbench. Charts via `recharts`.

## Views / Screens

### Screen: Workbench (single page, two tabs — Ask / Dashboard)

**Purpose:** Load a dataset, then either **Ask** questions (verified answers with tables/charts + code) or open the **Dashboard** tab to drag columns into a composable, saveable set of aggregated charts. A top-level **Ask / Dashboard** tab toggle switches the center region between the two modes (owned by the `dashboard-frontend` slice in `page.tsx`). The **EBCO Private Limited** header branding and the QuestionBox-pinned-to-bottom chat layout on the Ask tab are unchanged.

> **Note (current reality):** the reasoning LLM is now cloud **Gemini** per `.env`. The **Dashboard** tab and all **Export CSV** actions are **deterministic and use NO LLM** — they aggregate/export in-process over already-loaded datasets.

**Layout regions:**

- **Left sidebar — Datasets & Sessions**
  - **Real (Phase 2):** a list of **all** datasets loaded in the session (name, row count, column count), each with a **remove (×)** control. "Add dataset" opens the primary upload path — the `FileBrowser` "Browse my computer" modal (see below) — and adds another dataset to the same session.
  - **Real (Phase 3):** **Upload Excel** (now `.xlsx` accepted by the same browse/upload path), a **session picker** (`SessionPicker.tsx`, replaces the "Switch session" stub — lists prior sessions and reopens one with its datasets + history), and **Connect DB** (`ConnectDbModal.tsx` — read-only local DB table; may remain a **labelled Phase-4 stub** if that slice is cut).

- **FileBrowser modal — primary upload (real, `FileBrowser.tsx`)**
  - "Browse my computer" opens an in-app, home-confined file browser (`GET /local/browse`) with shortcuts (Home/Downloads/Documents/Desktop), an "↑ Up" control, folder navigation, and CSV files. Picking a file loads it via `POST /datasets/local`. This is the primary upload path (a reliable alternative to the OS dialog on Windows). Drag/drop multipart `POST /datasets` remains as a fallback.

- **Center — Ask tab (Conversation)**
  - **Upload panel (real):** "Browse my computer" (primary) / drag-drop fallback; on success shows the **profile card** (columns + types, row count, null/dup/outlier flags). Now accepts `.csv` **and** `.xlsx` (Phase 3).
  - **Question box (real):** pinned to the bottom of `<main>`; results scroll above. Text input → streams via `GET /ask/stream`.
  - **Live progress (real, Phase 2):** while a run is streaming, a **"Step 3 of 6" counter + elapsed timer** (fed by `step` SSE events) and the streaming answer text replace the old static "Analyzing…" spinner.
  - **Answer block (real):** written answer text, a **summary table**, and (where sensible) an auto-picked **chart** (bar/line/scatter from `chart_spec`).
  - **Export button (real, Phase 3):** on each `AnswerBlock`, a now-real **Export CSV** button (replaces the Phase-3 stub) that downloads the answer's `result_table` via `GET /queries/{id}/export`.
  - **Follow-up chips (real, Phase 2):** 2-3 clickable suggested questions under each answer (`GET /queries/{id}/followups`); clicking one asks it.
  - **Collapsible code panel (real, editable, Phase 2):** the exact generated Python; **editable** with a **Rerun** button (`POST /queries/{id}/rerun`).

- **Center — Dashboard tab (real, Phase 3 headline — `frontend/src/app/components/dashboard/*`)**
  - **Column palette:** draggable **column chips** built from the active dataset's profile — string / low-cardinality columns become **dimension** chips, numeric columns become **measure** chips (visually distinguished).
  - **Widget canvas (grid):** each **widget** has drop zones (one or more **dimensions**, one **measure**), an **aggregation selector** (`sum`/`avg`/`count`/`min`/`max`), and a **chart-type selector** (`bar`/`line`/`scatter`/`pie`/`table`). Dropping a valid combination calls `POST /dashboard/aggregate` and renders through the existing `recharts` `ChartView` (extended for **pie** and **table**). `count` needs no measure.
  - **Widget management:** add / remove / rearrange widgets in the grid; per-widget **Export CSV** (the widget's aggregated rows).
  - **Save / reload:** name the dashboard and **Save** (`POST /dashboards`); a **dashboard picker** lists saved dashboards (`GET /dashboards`) and reloads one (`GET /dashboards/{id}`) into the canvas; **PUT** on re-save, **DELETE** to remove.
  - Drag-and-drop via native HTML5 DnD or a DnD lib (`corepack pnpm add`), self-contained in the static export. Clean, EBCO-branded.

- **Right panel — Audit / History (real, read-only)**
  - List of prior questions for the session (`GET /sessions/{id}/queries`); clicking one loads its full record via `GET /queries/{id}`. Rerun rows appear as new entries.

**Actions available (Phase 3, real):** everything from Phase 2, plus — **build a dashboard** (drag columns → aggregate → chart, add/remove/rearrange widgets, save/name/reload), **export** an answer's or a widget's data as CSV, **ingest `.xlsx`**, and **resume a prior session** via the session picker. **Possibly labelled stub (if `db-connect` cut):** Connect DB (clearly tagged "Coming in Phase 4").

## Error States

- **Loading:** upload shows an inline spinner; asking shows the live **step counter + elapsed timer** (no longer a bare "Analyzing locally…" spinner).
- **Stream interrupted (disconnect):** if the browser is refreshed/closed mid-run the run is abandoned server-side and the lock released; the next question starts cleanly (no permanent 409 blocked state).
- **Ollama down (503):** banner "Local model unavailable — is Ollama running?" with the failed question preserved.
- **Bad file (400):** inline error on the upload panel.
- **Analysis failed (500):** the answer block shows the error plus, when available, the last code the agent tried and the execution error (transparency — "show where it got stuck").
- **Rerun error (400):** the edited code's sandbox error is shown inline under the code panel so the user can fix and rerun.
- **Dashboard invalid drop (400):** dropping a non-numeric column as a measure (or a missing column) shows an inline widget error ("pick a numeric measure") — the widget stays editable, never a crash.
- **Empty dashboard/answer export (400):** exporting a query/widget with no data shows an inline "nothing to export" note.
- **Connect DB stub (only if that slice is cut):** a small "Coming in Phase 4" toast — never a broken state.

## Tech Stack

Next.js 15 static export + React 19 + Tailwind (boilerplate) + `recharts` for charts (extended for pie/table in Phase 3). Drag-and-drop via native HTML5 DnD or a DnD lib added with `corepack pnpm add` (self-contained in the static export). Built with `corepack pnpm build`; served from `/app/`. E2E via `@playwright/test` in `frontend/tests/e2e/` (Phase 3: `phase3-dashboard.spec.ts`).
