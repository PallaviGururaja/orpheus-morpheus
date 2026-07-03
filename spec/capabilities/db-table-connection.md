# Capability: DB-Table Connection (Phase 3 — lowest priority; may defer to Phase 4)

> **Scope note:** this is the lowest-priority Phase-3 slice (`db-connect`). If it exceeds the phase budget it ships as a clearly-labelled **Phase-4 stub** (`POST /datasets/connect-db` returns 501; the "Connect DB" control shows a "Coming in Phase 4" toast) rather than half-built.

## What It Does
Connects read-only to a local PostgreSQL/SQLite database table and loads it as a dataset (profiled like any upload).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| connection details | JSON (local DSN, table) | `POST /datasets/connect-db` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_id + profile | JSON | UI + `datasets` (`source_type=db_table`) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local DB | Read-only SELECT into DuckDB/pandas | 400 with error surfaced |

## Business Rules
- Read-only — no writes back to the source DB, ever.
- Only local connections are accepted (localhost DSNs), consistent with the no-data-leaves constraint.

## Success Criteria
- [ ] Connecting a local table loads and profiles it identically to a CSV — `tests/phase3/test_db_connect.py`.
- [ ] A non-local DSN is rejected 400.
- [ ] A write attempt is impossible via this path (read-only enforced).
- [ ] If deferred: `POST /datasets/connect-db` returns 501 and the UI control is a labelled Phase-4 stub.
