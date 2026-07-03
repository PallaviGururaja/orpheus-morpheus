# Capability: Analyze Question (code-exec retry + verify)

## What It Does
Answers a plain-English question by planning a strategy, writing Python, running it locally against the dataset, inspecting and fixing-and-retrying until the result holds (bounded step limit), verifying the numbers reconcile, and returning a written answer + summary table + auto-picked chart + the exact code.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | Question box (`POST /ask`) | yes |
| session_id | string | UI | yes |
| dataset_ids | string[] | UI (one in Phase 1) | yes |
| profile | JSON | cached `datasets.profile` | yes |
| messages | turn history | session (see conversation-memory) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text | string | UI answer block + `queries.answer_text` |
| result_table | JSON rows | UI summary table + `queries.result_table` |
| chart_spec | JSON (type/x/y/series) or null | UI chart + `queries.chart_spec` |
| code | string | UI collapsible code + `queries.code` |
| verified, steps_used, tokens, elapsed_ms | mixed | UI + `queries` row |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Ollama (local) | plan / write_code / verify LLM calls | 503; set `error` → handle_error, failed audit row |
| Analysis engine | Execute generated Python in restricted namespace | Captured into `exec_error`, fed to retry loop (not fatal) |
| PostgreSQL | Write `queries` audit row | 500 (failed row still attempted) |

## Business Rules
- The write→execute→inspect loop is bounded by `max_steps` (default 6); exceeding it finalizes with `verified=false` and a flagged assumption rather than looping forever.
- The verify step reconciles headline numbers (totals/row counts) against the result; a mismatch triggers a bounded rewrite.
- Generated code runs in a restricted namespace (no fs/net/os) with datasets pre-bound; it must assign `result`.
- Same question + same data → same answer (deterministic: fixed model params, no randomness in the engine).
- On ambiguity, return a best-guess answer with the assumption flagged (and optionally a clarifying question) rather than blocking.

## Success Criteria
- [ ] For an aggregation question on a known CSV, `answer_text` and `result_table` match a hand-computed check.
- [ ] A question that first produces an execution error is recovered within the step limit (`steps_used > 1`, `verified=true`).
- [ ] The same question asked twice on the same dataset returns identical numbers.
- [ ] `chart_spec` is a bar chart for a categorical grouping and null when no chart is sensible.
- [ ] When Ollama is stopped, `POST /ask` returns 503 and a `failed` audit row is written.
