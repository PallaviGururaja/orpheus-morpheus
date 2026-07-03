# Capability: Large-Data Sampling (DuckDB) (Phase 4 — deferred)

> **Deferred from Phase 3.** The revised Phase 3 headline is the drag-and-drop dashboard builder; large-data out-of-core sampling moves to Phase 4 so Phase 3 stays a coherent, testable increment. Kept here as the Phase-4 spec.

## What It Does
Handles datasets from a few MB up to millions of rows via DuckDB out-of-core execution, using sampling/streaming when a full in-memory load is infeasible, and recording which path was used.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset (large) | file | dataset store | yes |
| question | string | `POST /ask` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer + result_table | mixed | UI |
| sampling note | string | UI + `queries` (records full-scan vs sampled) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| DuckDB | Out-of-core / sampled query | Captured into retry loop |

## Business Rules
- Above a configurable row/byte threshold, DuckDB streams from disk rather than loading fully into memory.
- Sampling is used only where a full scan is infeasible AND the question tolerates it (exact aggregates prefer full scan); the choice is recorded per query.
- Correctness over speed: default to full scan; sample only when necessary, and flag it.

## Success Criteria
- [ ] A ≥2,000,000-row dataset answers an aggregate question without exhausting memory.
- [ ] The gate fixture is large enough that a sampled answer and a full-scan answer are observably different, and the recorded note reflects which was used.
- [ ] Exact-aggregate questions use a full scan and match a ground-truth computation.
