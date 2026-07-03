# Capability: Multi-Dataset Analysis (Phase 2)

## What It Does
Loads several datasets in one session and answers questions that join, compare, or union them, auto-selecting the relevant dataset(s) from the profiles.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | `POST /ask` | yes |
| dataset_ids | string[] | session registry (multiple) | yes |
| profiles | JSON[] | cached `datasets.profile` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text / result_table / chart_spec | mixed | UI + `queries` |
| derived dataset | file + `datasets` row (`is_derived=true`) | dataset store |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Analysis engine | Join/union across DataFrames / DuckDB | Captured into retry loop |
| Ollama | plan selects datasets + join keys | 503 → handle_error |

## Business Rules
- The `plan` node loads every in-scope dataset's cached profile from the DB (keyed by table name), picks the minimal set needed, and names join keys from the profiles.
- Each in-scope dataset is registered as a named DuckDB table and a same-named namespace variable so generated code can JOIN/COMPARE/UNION across them.
- Additional datasets are added to a session via `POST /datasets/local` (primary, in-app browser) or `POST /datasets` with the same `session_id`; the sidebar lists all and can remove them.
- Derived tables created mid-analysis are registered and reusable in later turns.

## Success Criteria
- [ ] A join question over two related CSVs returns numbers matching a hand-computed join (a single-table answer is observably wrong) — `tests/phase2/test_multi_dataset.py`.
- [ ] The agent uses only the relevant dataset(s) when others are loaded.
- [ ] A derived table is persisted with `is_derived=true` and reusable in a follow-up.
- [ ] **`local_files.py` test debt cleared** (`tests/phase2/test_local_files.py`): `GET /local/browse` lists CSVs under a folder; `POST /datasets/local` loads a CSV by path; a path outside home is rejected 403; a non-CSV path is rejected 400.
