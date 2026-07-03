# Local Data-Analysis Agent

A personal, **fully-local** data-analysis agent. Upload a CSV, ask a question in plain
English, and get a verified, audited, reproducible answer — a written answer plus a
summary table plus (where sensible) an auto-picked chart, with the exact generated
Python shown. Nothing leaves the machine: reasoning runs on a local **Ollama** model
and analysis runs in-process via **DuckDB + pandas**. Every question, its code, its
result, and timing/token stats are persisted to a local **PostgreSQL** audit trail.

The project root **is** the app. All Python commands are run with `uv` from the repo
root (`C:\Users\dell\orpheus-morpheus`). The server binds to `127.0.0.1:8001` only.

## Architecture (Phase 1)

- **API** (FastAPI, `src/api/`): `POST /datasets` (upload + profile), `POST /ask`
  (run the agent), `GET /queries/{id}` and `GET /sessions/{id}/queries` (audit trail),
  `GET /health`. Serves the built frontend at `/app/`.
- **Agent** (LangGraph, `src/graph/`): `plan → write_code → execute_code → inspect`
  (bounded retry loop) `→ verify → finalize`, plus `handle_error`.
- **Analysis engine** (`src/analysis/`): CSV loader, profiler, restricted-namespace
  Python executor (blocks os/subprocess/socket/open), auto chart-type picker.
- **LLM** (`src/llm/providers/ollama.py`): OpenAI-compatible local Ollama, no API key.
- **Storage**: PostgreSQL (`sessions`, `datasets`, `queries`) via SQLAlchemy 2.0 +
  Alembic; dataset bytes on disk under `./data/datasets/<dataset_id>/`.

## Prerequisites

1. **Python + uv** — install [uv](https://docs.astral.sh/uv/).
2. **PostgreSQL** running locally with a `data_analyst` database:
   ```bash
   createdb data_analyst   # or: psql -U postgres -c "CREATE DATABASE data_analyst;"
   ```
3. **Ollama** installed and the model pulled (one-time; ~4-5 GB download):
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
   Ollama must be running at `http://localhost:11434`.
4. **Node + pnpm** (for building the frontend UI).

## Configuration (`.env`)

The repo reads settings with the `AGENT_` prefix from `.env`:

```
AGENT_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/data_analyst
AGENT_LLM_PROVIDER=ollama
AGENT_LLM_BASE_URL=http://localhost:11434/v1
AGENT_LLM_MODEL=qwen2.5-coder:7b
```

No API keys are needed — the LLM is local. No secrets are committed.

## Setup & run

```bash
# 1. Install Python dependencies
uv sync

# 2. Create the database schema (do NOT rely on auto-create)
uv run alembic upgrade head
uv run alembic current          # should print the head revision

# 3. Build the frontend static export (served at /app/)
cd frontend
pnpm install
pnpm build
cd ..

# 4. Start the app (binds 127.0.0.1:8001)
uv run python -m src
```

Then open **http://localhost:8001/app/**, upload a CSV, confirm the profile, and ask a
question (e.g. "What is the total revenue by region?").

## Tests

```bash
uv run pytest
```

Tests run against the **real** PostgreSQL driver and the **real** local Ollama model
from `.env` — no SQLite substitute, no stubbed LLM. Unit tests cover the profiler,
restricted executor (sandbox blocks), chart picker, settings, models, and API contract.
Integration tests (`tests/integration/`) exercise the full pipeline (upload → ask →
verified answer → persisted audit row → reproducibility) end-to-end.

If the Ollama model is still downloading / genuinely unreachable, the integration tests
**skip cleanly** (they never stub the model); every other test stays green.

## Data & privacy

Everything is local: PostgreSQL on `localhost`, dataset files under `./data`, LLM on
`localhost` Ollama. No network call leaves the machine during analysis.
