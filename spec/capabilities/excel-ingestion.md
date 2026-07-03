# Capability: Excel Ingestion (Phase 3)

## What It Does
Loads an Excel workbook (`.xlsx`) — selecting a sheet — as a dataset, profiled like a CSV.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | .xlsx (multipart) | `POST /datasets` | yes |
| sheet | string | UI (defaults to first) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_id + profile | JSON | UI + `datasets` (`source_type=excel`) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| openpyxl / pandas | Read sheet into DataFrame | 400 if unreadable |

## Business Rules
- Multi-sheet workbooks expose sheet selection; one sheet = one dataset.
- Flows through the same profiler and analysis path as CSV.

## Success Criteria
- [ ] An `.xlsx` loads with correct columns/types/row count.
- [ ] A chosen non-default sheet loads the right data.
