# Capability: Drag-and-Drop Dashboard Builder (Phase 3 — headline)

## What It Does
Lets the user drag dataset columns onto a canvas to build, arrange, name, save, and reload multiple aggregated charts (bar/line/scatter/pie/table) — with no typing and **no LLM**; aggregation is deterministic pandas/DuckDB.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | active dataset (session) | yes |
| dimensions | string[] (columns) | dragged dimension chips | no (empty → whole-dataset aggregate) |
| measure | string \| null | dragged measure chip | required unless `agg=count` |
| agg | `sum`\|`avg`\|`count`\|`min`\|`max` | widget selector | yes |
| chart_type | `bar`\|`line`\|`scatter`\|`pie`\|`table` | widget selector | yes |
| name + widgets | string + JSON | Save action | yes (on save) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| aggregated rows | JSON (`columns`, `rows`, `truncated`) | `POST /dashboard/aggregate` → `ChartView` |
| saved dashboard | `dashboard` row (`widgets` JSONB) | `POST/PUT /dashboards` |
| dashboard list / one dashboard | JSON | `GET /dashboards`, `GET /dashboards/{id}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas / DuckDB (`src/analysis/aggregate.py`) | group-by aggregate over the loaded dataset | 400 with validation error surfaced inline |
| PostgreSQL (`dashboard` table) | persist / load / delete dashboards | 404 / 400 |

_No LLM is involved in this capability._

## Business Rules
- **Deterministic, no LLM:** aggregation reuses `src/analysis` via a NEW `aggregate.py` helper (must not collide with `executor.py`); raw rows never leave the machine's process.
- Every named column (dimensions + measure) MUST exist in the dataset profile, else 400.
- `measure` may be null only when `agg=count`; a non-numeric measure is rejected 400.
- Output rows are capped (default 1000); overflow sets `truncated=true`.
- Chart-type is presentational only — it never changes the aggregated numbers.
- Palette chips are typed from the profile: string / low-cardinality → dimension, numeric → measure.
- A dashboard persists its full widget layout (specs + grid positions) as `widgets` JSONB and reloads identically.

## Success Criteria
- [ ] `POST /dashboard/aggregate` with `region`×`sum(revenue)` returns group totals matching a hand-computed pandas group-by over a fixture with several dimension groups (a wrong grouping is observably wrong) — `tests/phase3/test_dashboard.py`.
- [ ] `agg=count` with `measure=null` returns per-group row counts; a null measure with any other `agg` returns 400.
- [ ] A missing/non-existent column returns 400; a non-numeric measure returns 400.
- [ ] Saving then `GET /dashboards/{id}` returns byte-identical `widgets`; `PUT` updates and `DELETE` removes.
- [ ] E2E (`phase3-dashboard.spec.ts`): drag a dimension + measure into a widget, pick agg + bar, see the chart render; add a pie and a table widget; save, reload the page, reopen the dashboard, confirm it restores.
