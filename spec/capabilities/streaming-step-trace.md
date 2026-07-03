# Capability: Streaming Step Trace + Timer (Phase 2)

## What It Does
Streams the agent's progress live — a per-step trace, a "Step 3 of 6" counter, an elapsed timer, and streaming answer text — so the user sees what the agent is doing in real time.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question / session_id / dataset_ids | mixed | `GET /ask/stream` (SSE) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| step events | SSE (step index, total estimate, elapsed, node name) | UI step-counter/timer |
| answer tokens | SSE stream | UI streaming answer |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Ollama | Streamed completions | 503 event; close stream |
| Analysis engine | Executes per step | error event fed to inspect loop |

## Business Rules
- Events emit from each node via the observability layer; the total-step estimate updates as the loop iterates.
- If the client disconnects, the run still finishes and persists its audit row.

## Success Criteria
- [ ] The UI shows an advancing step counter and elapsed timer during a run.
- [ ] Answer text streams incrementally, then the final audit row matches the streamed answer.
