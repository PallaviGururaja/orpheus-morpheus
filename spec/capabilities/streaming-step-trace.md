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
- Events emit at each node transition via a runner-level wrapper over `agentic_ai.stream(...)`; the total-step estimate is `max_steps`.
- **Reclaimable lock (folded-in robustness fix):** a run whose client disconnects (refresh/close/dropped connection) or that exceeds its timeout must be marked `status="failed"` and release the per-session concurrency lock — it must NOT stay `pending` and block later `/ask` with a permanent 409. A 409 means a genuinely live run.

## Success Criteria
- [ ] The UI shows an advancing step counter and elapsed timer during a run.
- [ ] Answer text streams incrementally, then the final audit row matches the streamed answer.
- [ ] After a mid-run client disconnect, the abandoned query becomes `failed` and the next `/ask` on that session succeeds (no permanent 409) — covered by `tests/phase2/test_lock_reclaim.py`.
