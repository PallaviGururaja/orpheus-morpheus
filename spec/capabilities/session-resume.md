# Capability: Cross-Day Session Resume (Phase 3)

## What It Does
Lets the user close the app and later reopen a prior session with its datasets (including derived tables) and conversation history restored.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| — | — | `GET /sessions` (list) | — |
| session_id | string | session picker | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| session state | JSON (datasets + history) | UI workbench rehydrated |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| PostgreSQL | Read session, datasets, queries | 404 if missing |
| Dataset store | Rehydrate dataset files/derived tables | Skip missing file with a flag |

## Business Rules
- `GET /sessions` lists resumable sessions (title, dataset/query counts, `updated_at`); `GET /sessions/{id}` rehydrates datasets (with profiles) + query history.
- Datasets are reloaded from the on-disk store; derived tables are reconstructed or reloaded.
- Conversation history is restored into session memory so follow-ups continue seamlessly.
- The frontend **session picker** (`SessionPicker.tsx`, mounted in `Sidebar.tsx`) replaces the "Switch session" stub.

## Success Criteria
- [ ] `GET /sessions` returns prior sessions with dataset/query counts — `tests/phase3/test_session_resume.py`.
- [ ] `GET /sessions/{id}` restores its datasets (incl. derived) and question history; unknown id → 404.
- [ ] A follow-up in a resumed session has access to prior-turn context.
