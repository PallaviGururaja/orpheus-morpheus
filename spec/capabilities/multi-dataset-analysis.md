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
- The `plan` node picks the minimal set of datasets needed and names join keys from the profiles.
- Derived tables created mid-analysis are registered and reusable in later turns.

## Success Criteria
- [ ] A join question over two related CSVs returns numbers matching a hand-computed join.
- [ ] The agent uses only the relevant dataset(s) when others are loaded.
- [ ] A derived table is persisted with `is_derived=true` and reusable in a follow-up.
