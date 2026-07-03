# Architecture

---

## System Overview

A single-user, fully-local web application. A React static build (served by FastAPI at `http://localhost:8001/app/`) is the desktop-style UI. The FastAPI backend ingests data files, profiles them, and runs a LangGraph analysis agent for each question. The agent reasons via a **local Ollama** model over an OpenAI-compatible endpoint and executes generated Python **in-process** against DuckDB + pandas. All history — sessions, datasets, and every question/code/result — is persisted to a **local PostgreSQL** database for audit and reproducibility. No component makes any off-device network call.

## Component Map

```
Browser (React static @ /app/)
        │  HTTP (localhost:8001)
        ▼
FastAPI backend ───────────────► LangGraph analysis agent
   │  (upload/profile/ask/audit)      │  plan→write_code→execute→inspect↻→verify
   │                                  ▼
   │                          Analysis engine (DuckDB + pandas, restricted namespace)
   │                                  │
   │                                  ▼
   │                          Local Ollama  (http://localhost:11434/v1)
   ▼
Local PostgreSQL  (sessions, datasets, queries/audit trail)
        ▲
Dataset store (on-disk uploaded/derived files under ./data)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (React static export) | Upload, profile view, question box, answer/table/chart render, collapsible code, labelled stubs |
| API (FastAPI) | Endpoints for upload+profile, ask, audit retrieval; request/response logging; serves `/app/` |
| Agent (LangGraph) | Plan → write code → execute → inspect/retry (bounded) → verify → finalize |
| Analysis engine | DuckDB + pandas execution in a restricted namespace; profiling; chart selection |
| LLM (Ollama provider) | Local reasoning/code generation via OpenAI-compatible `/v1/chat/completions` |
| Storage | PostgreSQL for app history/audit; on-disk dataset store for file bytes/derived tables |

## Data Flow

1. **Trigger:** user uploads a CSV via the UI → `POST /datasets`.
2. Backend stores the file, loads it into the analysis engine, runs the profiler (columns, types, ranges, row count, null/dup/outlier flags), writes a `datasets` row, returns the profile.
3. User submits a question → `POST /ask` (bound to the session + dataset).
4. The LangGraph agent plans, writes Python, executes it in the restricted namespace, inspects the result, fixes-and-retries up to the step limit, then verifies (row counts/totals reconcile).
5. **Output:** written answer + summary table + auto-picked chart spec returned to the UI; a `queries` audit row (question, final code, result, timestamps, tokens, elapsed) is persisted.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Ollama (`localhost:11434/v1`) | Local LLM reasoning/code gen | `POST /ask` returns 503 with a clear "local model unavailable — is Ollama running?" message |
| PostgreSQL (`localhost:5432`) | App history + audit trail | Startup/health fails fast; endpoints return 500 with driver error surfaced in logs |
| DuckDB + pandas (in-process) | Analysis execution engine | Execution errors are captured and fed back into the agent's inspect/retry loop |

## Stack

- **Language:** Python 3.12+ (backend); TypeScript/React (frontend).
- **Agent framework:** LangGraph.
- **LLM provider + model:** Local **Ollama** via OpenAI-compatible endpoint — `AGENT_LLM_BASE_URL=http://localhost:11434/v1`, `AGENT_LLM_MODEL=qwen2.5-coder:7b`, **no API key**. A new `ollama` provider is added to `src/llm/providers/` and registered in `src/llm/client.py` alongside the existing `anthropic`/`gemini`.
- **Backend:** FastAPI, run via `uv run python -m src` (uvicorn `api:app` on `127.0.0.1:8001`), serving the frontend static export at `/app/`.
- **Database + ORM:** **Local PostgreSQL** + SQLAlchemy 2.0, driver **`postgresql+psycopg`** (psycopg 3). `AGENT_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/data_analyst`. Alembic for migrations. **This replaces the boilerplate SQLite default** — `src/db/session.py` must not assume SQLite (no SQLite-only connect args); schema is created via `uv run alembic upgrade head`, not `init_db()` auto-create.
- **Frontend:** Next.js 15 static export (React 19) built with `pnpm build`, served from `/app/`. Charts via a lightweight React chart lib.
- **Dependency management:** `uv` + `pyproject.toml` (Python); `pnpm` (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | latest | Agent graph orchestration |
| duckdb | latest | Analytics engine (SQL + out-of-core/sampling later) |
| pandas | latest | DataFrame manipulation + result shaping |
| openpyxl | latest | Excel ingestion (Phase 3) |
| psycopg[binary] | 3.x | PostgreSQL driver (`postgresql+psycopg`) |
| sqlalchemy | 2.0.x | ORM for app history/audit |
| alembic | latest | DB migrations |
| httpx (or openai) | latest | Ollama OpenAI-compatible `/v1/chat/completions` calls |
| recharts | latest | Frontend chart rendering (bar/line/scatter) |
| @playwright/test | latest | Frontend E2E smoke tests |

**Avoid:** any cloud LLM SDK path for this project (Anthropic/Gemini providers stay in the tree but are unused — the active provider is `ollama`); SQLite as a PostgreSQL substitute; unrestricted `exec` of generated code (must use the restricted namespace); any outbound network call other than to `localhost` Ollama.

## Deployment Model

Long-running local process on the user's Windows 11 machine: `uv run python -m src` serves API + static UI on `127.0.0.1:8001`. PostgreSQL and Ollama run as local services. Nothing is deployed to any cloud.

> **Assumed:** uploaded and derived dataset files are stored on disk under `./data/datasets/<dataset_id>/`; PostgreSQL stores metadata + audit, not raw file bytes.
> **Assumed:** the frontend chart library is `recharts`; swap-able without spec change since the API returns a neutral chart spec (type + series), not a rendered chart.
