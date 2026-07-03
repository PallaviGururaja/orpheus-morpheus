# API

---

## API Style

REST (FastAPI), JSON, served on `127.0.0.1:8001`. All responses use the boilerplate envelope: success → `{"data": {...}}`; error → `{"detail": {"code": "...", "message": "..."}}` with the appropriate HTTP status. The frontend static build is served at `/app/`. This is the API contract the `frontend` slice builds against; it can be built concurrently with the backend.

## Endpoints / Commands

### Phase 1 — real

### `POST /datasets`
**Purpose:** Upload one CSV, store it, profile it, return the profile. Creates a session if `session_id` is omitted.

**Request:** `multipart/form-data` — `file` (CSV), optional `session_id`.

**Response:**
```json
{ "data": {
  "session_id": "uuid",
  "dataset_id": "uuid",
  "name": "sales.csv",
  "row_count": 12000,
  "column_count": 8,
  "profile": { "columns": [ {"name": "region", "dtype": "string", "null_pct": 0.0, "distinct": 4} ],
               "duplicate_rows": 3, "flags": ["3 duplicate rows"] }
}}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Not a CSV / unparseable file |
| 500 | Storage or DB failure |

### `POST /ask`
**Purpose:** Run the analysis agent for one question against the session's dataset(s). Returns written answer + summary table + chart spec + generated code.

**Request:**
```json
{ "session_id": "uuid", "dataset_ids": ["uuid"], "question": "Total revenue by region?" }
```

**Response:**
```json
{ "data": {
  "query_id": "uuid",
  "answer_text": "Total revenue is 1.2M, led by West (480K)…",
  "result_table": [ {"region": "West", "revenue": 480000} ],
  "chart_spec": { "type": "bar", "x": "region", "y": "revenue" },
  "code": "result = df.groupby('region')['revenue'].sum().reset_index()",
  "verified": true,
  "steps_used": 2,
  "prompt_tokens": 850, "completion_tokens": 120, "elapsed_ms": 4100
}}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing question / unknown dataset |
| 409 | A run is already in progress for this session |
| 503 | Ollama unavailable ("local model unavailable — is Ollama running?") |
| 500 | Unhandled failure (a `failed` audit row is still written) |

### `GET /queries/{query_id}`
**Purpose:** Retrieve one persisted audit record (question, exact code, result, timing, tokens).

**Response:** the full `Query` entity (see `spec/data.md`).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such query |

### `GET /sessions/{session_id}/queries`
**Purpose:** List the audit trail for a session (for the history panel + reproducibility review).

**Response:** `{ "data": { "queries": [ {"query_id": "...", "question": "...", "created_at": "...", "verified": true} ] } }`

### `GET /health`
**Purpose:** Liveness (boilerplate). Extended to report PostgreSQL and Ollama reachability.

### Phase 2 — stubbed in Phase 1 (return 501 Not Implemented with a clear message)

- `GET /ask/stream` — SSE stream of step-trace events (step index, total estimate, elapsed, streamed answer tokens).
- `POST /queries/{query_id}/rerun` — execute user-edited code in the same restricted namespace; writes a new audit row (`is_rerun=true`).
- `GET /queries/{query_id}/followups` — 2-3 suggested follow-up questions (delivered inline on `/ask` once real).

### Phase 3 — stubbed in Phase 1 (return 501)

- `POST /datasets/connect-db` — read-only local DB-table connection.
- `POST /datasets` with `.xlsx` — Excel ingestion.
- `GET /queries/{query_id}/export.csv` — download derived dataset/chart data as CSV.
- `GET /sessions` — list resumable sessions for cross-day resume.

## Authentication

None — single-user local app bound to `127.0.0.1`. No auth layer; access control is the OS/local machine boundary.
