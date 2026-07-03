# Capability: Profile Dataset on Load

## What It Does
On CSV upload, automatically inspects the data and returns a profile (columns, types, ranges, row count) plus data-quality flags (nulls, duplicates, outliers, odd types).

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | CSV (multipart) | Upload UI (`POST /datasets`) | yes |
| session_id | string | UI (created if absent) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| profile | JSON (per-column type/range/null%/distinct, dup count, flags) | UI profile card + `datasets.profile` |
| dataset_id, row_count, column_count | ids/ints | UI + `datasets` row |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Analysis engine (pandas/DuckDB) | Load CSV, compute profile | 400 if unparseable; 500 on storage/DB error |
| PostgreSQL | Insert `datasets` row | 500 (surfaced) |

## Business Rules
- Row count and column count are computed from the FULL file, not a sample (Phase 1 files are small; large-file sampling is Phase 3).
- Quality flags include at least: columns with nulls (% each), count of fully-duplicate rows, columns whose declared type looks wrong (e.g. numeric-in-string).
- Profile is cached on the `datasets` row so the ask-graph reuses it without recomputing.

## Success Criteria
- [ ] Uploading a known CSV returns the exact column names, correct dtypes, and exact row count.
- [ ] A CSV with injected null cells and duplicate rows produces the corresponding flags.
- [ ] The profile persists to `datasets.profile` and is returned unchanged on the response.
