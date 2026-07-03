# Capability: Persist Audit Trail

## What It Does
Records every analysis run — question, exact code, result, chart, status, timestamps, tokens, and elapsed time — to PostgreSQL so any answer can be reviewed and reproduced later.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| run outputs | AgentState fields | finalize/handle_error nodes | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| queries row | DB record | PostgreSQL `queries` |
| record | JSON | `GET /queries/{id}`, `GET /sessions/{id}/queries` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| PostgreSQL | Insert/update `queries` | 500; logged with run_id |

## Business Rules
- A `queries` row is created at run start (`pending`) and updated to `completed`/`failed` at the end — even a failed/503 run leaves a durable row with `error_message`.
- The persisted `code` is the exact code executed (or user-edited on rerun in Phase 2).
- Token counts come from the Ollama response usage; `elapsed_ms` is wall-clock for the run.

## Success Criteria
- [ ] After any `POST /ask`, `GET /queries/{id}` returns the question, exact code, result, tokens, and elapsed_ms.
- [ ] A failed run (Ollama down) still yields a retrievable `failed` record with `error_message`.
- [ ] `GET /sessions/{id}/queries` lists all runs for the session in order.
