# Data Model

---

## Storage Technology

**Local PostgreSQL** (`postgresql+psycopg://postgres:postgres@localhost:5432/data_analyst`) via SQLAlchemy 2.0 + Alembic, for all app history and the audit trail. Raw dataset bytes and derived tables live on disk under `./data/datasets/<dataset_id>/`; PostgreSQL stores metadata and the profile only. Schema is created via `uv run alembic upgrade head` (not runtime auto-create).

> **Note:** this replaces the boilerplate SQLite `runs` table. The `runs` table/`RunRow` capability slot is repurposed into the `queries` audit entity below.

## Entities

### Entity: Session

A persistent workbench a user returns to; owns datasets and the query history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | text (uuid) | yes | Primary key |
| title | text | no | User/auto label (e.g. "Sales analysis") |
| created_at | timestamptz | yes | Creation time |
| updated_at | timestamptz | yes | Last activity |

### Entity: Dataset

A loaded data source (CSV in Phase 1; Excel/DB table later) bound to a session, with its cached profile.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | text (uuid) | yes | Primary key |
| session_id | text (fk → Session.id) | yes | Owning session |
| name | text | yes | Original filename / table name |
| source_type | text | yes | `csv` \| `excel` \| `db_table` (csv in Phase 1) |
| storage_path | text | yes | On-disk path to the stored file/derived table |
| row_count | bigint | yes | Rows detected at profile time |
| column_count | int | yes | Columns detected |
| profile | jsonb | yes | Full profile: per-column type, range, null %, distinct count; dup/outlier flags |
| is_derived | boolean | yes | True if created mid-session by the agent |
| created_at | timestamptz | yes | Load time |

### Entity: Query (audit record)

One row per analysis run — the full audit trail: question, exact code, result, timing, tokens.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | text (uuid) | yes | Primary key (= `run_id`) |
| session_id | text (fk → Session.id) | yes | Owning session |
| dataset_ids | jsonb | yes | Datasets in scope for this question |
| question | text | yes | User's plain-English question |
| plan | text | no | Strategy text from the plan node |
| code | text | no | Final generated (or user-edited) Python |
| result_table | jsonb | no | Summary-table rows returned |
| answer_text | text | no | Written answer |
| chart_spec | jsonb | no | Chart type + series, or null |
| verified | boolean | yes | Did numbers reconcile |
| status | text | yes | `pending` \| `completed` \| `failed` |
| error_message | text | no | Set when status = failed |
| steps_used | int | no | How many loop steps were taken |
| prompt_tokens | int | no | Summed prompt tokens (from Ollama usage) |
| completion_tokens | int | no | Summed completion tokens |
| elapsed_ms | int | no | Wall-clock duration |
| is_rerun | boolean | yes | True if from edit-and-rerun (Phase 2), default false |
| created_at | timestamptz | yes | Run start |
| completed_at | timestamptz | no | Run end |

### Relationships

- `Session 1 ── N Dataset` (cascade delete datasets with session).
- `Session 1 ── N Query`.
- `Query.dataset_ids` references datasets by id (many-to-many captured as a jsonb id list; a physical join table is unnecessary for a single-user local tool).

## Data Lifecycle

- **Create:** session on first upload; dataset on each upload/profile; query on each `POST /ask`.
- **Update:** query row updated from `pending` → `completed`/`failed` at finalize; session `updated_at` bumped on activity.
- **Derived datasets:** created mid-session by the agent, stored with `is_derived=true`, tied to the session.
- **Delete:** deleting a session cascades its datasets (and their on-disk files) and queries. Nothing is auto-expired — audit history is retained for reproducibility.

## Sensitive Data

The datasets may contain personal/business data, but by design **all storage is local** — PostgreSQL on `localhost`, files under `./data`, LLM on `localhost` Ollama. No secrets are stored in the DB (Ollama needs no API key). The `.env` holds the local DB DSN only. No PII leaves the machine.
