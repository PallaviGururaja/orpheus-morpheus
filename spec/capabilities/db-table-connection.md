# Capability: DB-Table Connection (Phase 3)

## What It Does
Connects read-only to a local database table and loads it as a dataset (profiled like any upload).

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
- [ ] Connecting a local table loads and profiles it identically to a CSV.
- [ ] A write attempt is impossible via this path (read-only enforced).
