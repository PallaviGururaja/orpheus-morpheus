# API

---

## API Style

REST (FastAPI), JSON, served on `127.0.0.1:8001`. All responses use the boilerplate envelope: success → `{"data": {...}}`; error → `{"detail": {"code": "...", "message": "..."}}` with the appropriate HTTP status. The frontend static build is served at `/app/`. This is the API contract the `frontend` slice builds against; it can be built concurrently with the backend.

## Endpoints / Commands

### Phase 1 — real

### `POST /datasets`
**Purpose:** Upload one CSV via multipart, store it, profile it, return the profile. Creates a session if `session_id` is omitted. Adding a second/third dataset to an existing session (multi-dataset) is done by passing the same `session_id`.

**Request:** `multipart/form-data` — `file` (CSV), optional `session_id`. (Note: as shipped, the frontend `<input>` no longer enforces a CSV-only `accept` filter client-side; the server validates the file.)

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

### `GET /local/browse` — real (shipped)
**Purpose:** In-app file browser for local CSVs (the primary upload path — a reliable alternative to the OS dialog). Lists sub-folders and CSV files under a directory, **confined to the user's home folder**.

**Request:** query param `path` (optional) — absolute folder path; omitted → home.

**Response:**
```json
{ "data": {
  "cwd": "C:/Users/me/Downloads",
  "parent": "C:/Users/me",
  "shortcuts": [ {"label": "Home", "path": "C:/Users/me"}, {"label": "Downloads", "path": "C:/Users/me/Downloads"} ],
  "dirs":  [ {"name": "reports", "path": "C:/Users/me/Downloads/reports"} ],
  "files": [ {"name": "orders.csv", "path": "C:/Users/me/Downloads/orders.csv", "size": 20481} ]
}}
```
Dot-files are hidden; only `.csv` files are listed. `parent` is `null` at the home root or when the parent would escape home.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 403 | `path` resolves outside the home folder, or a folder can't be opened (permission) |
| 400 | `path` is not a folder |

### `POST /datasets/local` — real (shipped)
**Purpose:** Load a CSV already on disk (chosen via `GET /local/browse`) as a dataset. Same profile/response shape as `POST /datasets`. Creates a session if `session_id` is omitted; reuses/creates the given `session_id` otherwise.

**Request:** JSON — `{ "path": "C:/Users/me/Downloads/orders.csv", "session_id": "uuid" | null }`.

**Response:** identical shape to `POST /datasets` (`session_id`, `dataset_id`, `name`, `row_count`, `column_count`, `profile`).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 403 | `path` resolves outside the home folder |
| 400 | Not a `.csv` file / empty / unparseable |

### `POST /ask`
**Purpose:** Run the analysis agent for one question against the session's dataset(s). `dataset_ids` is a **list**; when it holds more than one id (multi-dataset), each dataset is registered as a named DuckDB table and exposed as a named DataFrame so generated code can JOIN/COMPARE/UNION across them. An empty/omitted `dataset_ids` defaults to all datasets in the session. Returns written answer + summary table + chart spec + generated code.

**Request:**
```json
{ "session_id": "uuid", "dataset_ids": ["uuid-orders", "uuid-customers"], "question": "average order value per customer segment" }
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
| 409 | A run is genuinely still in progress for this session. **The lock is now reclaimable:** if the holding run has been abandoned (client disconnected / exceeded the run timeout), it is marked `failed` and its lock released so this request proceeds instead of returning 409 forever. A 409 therefore means a live run, not a stuck one. |
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

### Phase 2 — real

### `GET /ask/stream`
**Purpose:** Same analysis as `POST /ask`, but streams live step-trace events and the answer via **Server-Sent Events** (`Content-Type: text/event-stream`), so the UI can show a "Step 3 of 6" counter, an elapsed timer, and the streaming answer. Honors the same session concurrency lock and the same reclaimable-lock behaviour as `POST /ask`. When the client disconnects mid-stream, the run is marked `failed` and the lock released (no permanent 409).

**Request:** query params `session_id`, `dataset_ids` (repeated or comma-separated), `question`. (GET is used so `EventSource` can consume it; an equivalent `POST` body form is acceptable if the frontend uses `fetch`+`ReadableStream`.)

**SSE event schema** — each message is `event: <type>\ndata: <json>\n\n`:
| `event:` type | `data` JSON | Meaning |
|--------------|-------------|---------|
| `step` | `{ "step": 3, "total_estimate": 6, "node": "write_code", "elapsed_ms": 2100 }` | A graph node started/finished; drives the "Step 3 of 6" counter + timer |
| `token` | `{ "text": "Total revenue is…" }` | A chunk of the streaming answer text (append in order) |
| `done` | the full `POST /ask` `data` payload (`query_id`, `answer_text`, `result_table`, `chart_spec`, `code`, `verified`, `steps_used`, tokens, `elapsed_ms`) | Run finished successfully; the persisted audit row id is `query_id` |
| `error` | `{ "code": "MODEL_UNAVAILABLE"｜"CONFLICT"｜"INTERNAL", "message": "…" }` | Terminal error; stream ends (mirrors the `POST /ask` status codes) |

`total_estimate` is the node budget (`max_steps`, default 6); `step` is 1-based and monotonic.

### `GET /queries/{query_id}/followups`
**Purpose:** Generate 2-3 suggested follow-up questions for a completed query (rendered as clickable chips). Computed post-hoc from the original question + answer + dataset profile via a standalone `generate_followups` helper (not a node in the ask-graph). Non-fatal: on model failure returns an empty list, not an error.

**Response:** `{ "data": { "followups": ["Break this down by month", "Show the top 5 only"] } }`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such query |

### `POST /queries/{query_id}/rerun`
**Purpose:** Execute user-edited Python against the same session/datasets in the same restricted namespace as the original run, and record a **NEW** audit row (`is_rerun=true`) rather than mutating the original — preserving the audit trail.

**Request:** `{ "code": "result = df.groupby('segment')['aov'].mean().reset_index()" }`

**Response:** a `POST /ask`-shaped `data` payload for the new run: `query_id` (the new row), `answer_text` (regenerated from the new result), `result_table`, `chart_spec`, `code` (the edited code), `verified`, `steps_used` (1), tokens, `elapsed_ms`.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such original query |
| 400 | Empty/invalid code, or the edited code raised in the sandbox (the execution error is returned so the user can fix it) |
| 409 | A run is in progress for the session (same reclaimable lock as `/ask`) |

### Phase 3 — stubbed in Phase 1 (return 501)

- `POST /datasets/connect-db` — read-only local DB-table connection.
- `POST /datasets` with `.xlsx` — Excel ingestion.
- `GET /queries/{query_id}/export.csv` — download derived dataset/chart data as CSV.
- `GET /sessions` — list resumable sessions for cross-day resume.

## Authentication

None — single-user local app bound to `127.0.0.1`. No auth layer; access control is the OS/local machine boundary.
