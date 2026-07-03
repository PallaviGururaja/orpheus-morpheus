# Capability: Session Conversation Memory

## What It Does
Carries prior question/answer turns within a session into each new question so follow-ups have context (e.g. "and by month?" after "total revenue by region").

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | string | UI | yes |
| prior turns | queries history | PostgreSQL `queries` | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| messages | turn list | AgentState `messages`, into the plan/write_code prompts |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| PostgreSQL | Read recent `queries` for the session | Non-fatal — proceed with empty history, log |

## Business Rules
- A bounded sliding window of the last K (default 5) question/answer pairs is loaded — raw data is never injected, only prior questions/answers and the current profile.
- Turn history is scoped to the session; other sessions are never mixed in.

## Success Criteria
- [ ] A follow-up question that references a prior turn ("and by month?") produces an answer consistent with the prior question's subject.
- [ ] A brand-new session sends no prior turns.
