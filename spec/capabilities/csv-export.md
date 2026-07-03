# Capability: CSV Export (Phase 3)

## What It Does
Downloads a persisted answer's result table, or a dashboard widget's aggregated data, as a CSV file. **No LLM** — deterministic serialization of already-computed rows.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_id | string | AnswerBlock Export button | yes (answer export) |
| dashboard_id + widget_id | string + string | dashboard widget Export button | yes (widget export) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| CSV file | download (`text/csv`) | `GET /queries/{id}/export` |
| CSV file | download (`text/csv`) | `GET /dashboards/{id}/widgets/{widget_id}/export` (or client-side blob of the widget's fetched rows) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| PostgreSQL | Read `queries.result_table` / `dashboard.widgets` | 404 if missing |
| pandas/DuckDB | Recompute the widget aggregate for server-side export | 400 if the spec is no longer valid |

## Business Rules
- Query export streams the persisted `result_table` byte-for-byte reproducibly from the audit row; a query with no `result_table` (failed run) returns 400.
- Widget export recomputes the widget's `POST /dashboard/aggregate` spec server-side (or the frontend serializes the widget's already-fetched rows as a client-side blob).
- The Export button on `AnswerBlock` replaces the earlier Phase-3 stub.

## Success Criteria
- [ ] `GET /queries/{id}/export` downloads a CSV whose rows match the query's `result_table` — `tests/phase3/test_export.py`.
- [ ] A query with no result returns 400.
- [ ] A dashboard widget export returns a CSV whose rows match `POST /dashboard/aggregate` for the same spec.
