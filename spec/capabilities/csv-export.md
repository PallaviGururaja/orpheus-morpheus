# Capability: CSV Export (Phase 3)

## What It Does
Downloads a derived dataset or an answer's chart/table data as a CSV file.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_id | string | UI | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| CSV file | download | `GET /queries/{id}/export.csv` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Dataset store / DB | Read result table | 404 if no result |

## Business Rules
- Exports the persisted `result_table` (or a referenced derived dataset), byte-for-byte reproducible from the audit row.

## Success Criteria
- [ ] Exporting a prior answer downloads a CSV whose rows match `result_table`.
