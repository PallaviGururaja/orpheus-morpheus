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

### Phase 3 — real

> **Note (current reality):** the reasoning LLM is now cloud **Gemini** per `.env`. The dashboard-aggregation and export endpoints below are **deterministic and use NO LLM** — they compute in-process via pandas/DuckDB over already-loaded datasets.

#### Dashboard builder (slice `dashboard-backend`)

### `POST /dashboard/aggregate`
**Purpose:** Deterministically aggregate one loaded dataset for a single dashboard widget. **No LLM.** Reuses `src/analysis` (new `aggregate.py` helper) over pandas/DuckDB. Validates that every named column exists in the dataset profile, caps output rows, and handles the no-measure `count` case.

**Request:**
```json
{
  "dataset_id": "uuid",
  "dimensions": ["region", "category"],
  "measure": "revenue",
  "agg": "sum",
  "chart_type": "bar"
}
```
- `dimensions`: 0+ grouping columns (string / low-cardinality). Empty → a single aggregate row over the whole dataset.
- `measure`: numeric column to aggregate, or `null` when `agg` is `count`.
- `agg`: one of `sum` | `avg` | `count` | `min` | `max`.
- `chart_type`: one of `bar` | `line` | `scatter` | `pie` | `table` (echoed back; does not change the numbers).

**Response:**
```json
{ "data": {
  "columns": ["region", "category", "revenue"],
  "rows": [ {"region": "West", "category": "A", "revenue": 480000} ],
  "agg": "sum",
  "measure": "revenue",
  "dimensions": ["region", "category"],
  "chart_type": "bar",
  "row_count": 12,
  "truncated": false
}}
```
`truncated` is `true` when the result exceeded the output-row cap (default 1000) and was clipped.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Unknown `agg`/`chart_type`; a named column is not in the dataset profile; `measure` null while `agg` ≠ `count`; `measure` non-numeric |
| 404 | Unknown `dataset_id` |

### `POST /dashboards`
**Purpose:** Persist a named dashboard (its widget layout + specs) to the `dashboard` table.

**Request:** `{ "session_id": "uuid", "name": "Sales overview", "widgets": [ { "id": "w1", "dimensions": ["region"], "measure": "revenue", "agg": "sum", "chart_type": "bar", "layout": {"x": 0, "y": 0, "w": 6, "h": 4} } ] }`

**Response:** `{ "data": { "id": "uuid", "session_id": "uuid", "name": "Sales overview", "widgets": [ … ], "created_at": "…" } }`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing name / malformed widgets |
| 404 | Unknown `session_id` |

### `GET /dashboards`
**Purpose:** List saved dashboards (optionally `?session_id=uuid`) for the dashboard picker.

**Response:** `{ "data": { "dashboards": [ {"id": "uuid", "session_id": "uuid", "name": "Sales overview", "created_at": "…"} ] } }`

### `GET /dashboards/{id}`
**Purpose:** Load one saved dashboard with its full `widgets` JSONB for reload.

**Response:** the full `Dashboard` entity (see `spec/data.md`).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such dashboard |

### `PUT /dashboards/{id}`
**Purpose:** Update a dashboard's name and/or widgets (save edits/rearrangement).

**Request:** `{ "name": "Sales overview", "widgets": [ … ] }` — same widget shape as `POST /dashboards`.

**Response:** the updated `Dashboard` entity.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such dashboard |
| 400 | Malformed widgets |

### `DELETE /dashboards/{id}`
**Purpose:** Delete a saved dashboard.

**Response:** `{ "data": { "deleted": true } }`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such dashboard |

#### CSV export (slice `export`)

### `GET /queries/{query_id}/export`
**Purpose:** Download a persisted query's `result_table` as a CSV file. **No LLM.** Byte-for-byte reproducible from the audit row.

**Response:** `Content-Type: text/csv`, `Content-Disposition: attachment; filename="query-<id>.csv"`; body = the `result_table` rows as CSV (header row from the table's keys).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such query |
| 400 | Query has no `result_table` (e.g. failed run) |

### `GET /dashboards/{id}/widgets/{widget_id}/export`
**Purpose:** Download one dashboard widget's aggregated data as CSV. Recomputes the widget's `POST /dashboard/aggregate` spec server-side and streams the rows. (The frontend MAY instead export the widget's already-fetched rows as a client-side blob; this endpoint is the server-side equivalent for parity/testing.)

**Response:** `Content-Type: text/csv`, `Content-Disposition: attachment; filename="widget-<widget_id>.csv"`.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such dashboard or widget id |
| 400 | Widget spec no longer valid against the dataset |

#### Excel ingestion (slice `excel`)

### `POST /datasets` with `.xlsx` — real
**Purpose:** The existing multipart upload now accepts `.xlsx` in addition to `.csv`. Loads the first sheet by default; an optional `sheet` form field selects another sheet. Same profile/response shape as the CSV path. `source_type` is recorded as `excel`.

**Request:** `multipart/form-data` — `file` (`.csv` or `.xlsx`), optional `session_id`, optional `sheet` (name or index; Excel only).

**Response:** identical shape to the CSV `POST /datasets`.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Unreadable workbook / unknown `sheet` / unsupported extension |

### `GET /local/browse` + `POST /datasets/local` — now list/accept `.xlsx`
**Purpose:** The in-app file browser now lists `.xlsx` alongside `.csv`, and `POST /datasets/local` loads an `.xlsx` by path (optional `sheet` in the JSON body). Same response shapes as the CSV path.

**Error cases:** as the CSV path, plus `400` for unknown `sheet`.

#### Session resume (slice `session-resume`)

### `GET /sessions`
**Purpose:** List resumable sessions for the session picker.

**Response:** `{ "data": { "sessions": [ {"id": "uuid", "title": "Sales analysis", "dataset_count": 2, "query_count": 14, "updated_at": "…"} ] } }`

### `GET /sessions/{session_id}`
**Purpose:** Load/rehydrate a prior session — its datasets (with profiles) and query history — so the workbench can restore state.

**Response:**
```json
{ "data": {
  "session": {"id": "uuid", "title": "Sales analysis", "updated_at": "…"},
  "datasets": [ {"dataset_id": "uuid", "name": "orders.csv", "row_count": 12000, "column_count": 8, "profile": { … }, "source_type": "csv"} ],
  "queries": [ {"query_id": "uuid", "question": "…", "created_at": "…", "verified": true} ]
}}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No such session |

#### DB-table connection (slice `db-connect`, lowest priority — may ship as a labelled Phase-4 stub)

### `POST /datasets/connect-db`
**Purpose:** Read-only connect to a **local** PostgreSQL/SQLite and load one table as a dataset, profiled like any upload. Read-only — never writes back. `source_type` = `db_table`.

**Request:** `{ "dsn": "postgresql://localhost:5432/mydb" | "sqlite:///C:/path/db.sqlite", "table": "orders", "session_id": "uuid" | null }`

**Response:** identical shape to `POST /datasets` (`session_id`, `dataset_id`, `name` = table name, `row_count`, `column_count`, `profile`).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Non-local DSN rejected; unknown table; connection/read error surfaced |
| 501 | If shipped as a deferred Phase-4 stub, returns 501 with a "coming in Phase 4" message |

## Authentication

None — single-user local app bound to `127.0.0.1`. No auth layer; access control is the OS/local machine boundary.
