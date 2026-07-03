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
- Multi-sheet workbooks expose sheet selection; one sheet = one dataset. Default = first sheet.
- Accepted by BOTH the multipart `POST /datasets` and the in-app `GET /local/browse` + `POST /datasets/local` paths (`.xlsx` added to the loader's extension allow-list).
- The Excel branch lives in the shared loader (`src/analysis/ingest.py`); it does not otherwise change `local_files.py` beyond the extension allow-list.
- Flows through the same profiler and analysis path as CSV. `openpyxl` is already a dependency.

## Success Criteria
- [ ] An `.xlsx` loads with correct columns/types/row count via `POST /datasets` — `tests/phase3/test_excel.py`.
- [ ] A chosen non-default `sheet` loads the right data.
- [ ] `GET /local/browse` lists `.xlsx` files and `POST /datasets/local` loads one by path.
- [ ] The "Upload Excel" stub is removed; the upload `<input>` accepts `.xlsx`.
