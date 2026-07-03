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
- Datasets are reloaded from the on-disk store; derived tables are reconstructed or reloaded.
- Conversation history is restored into session memory so follow-ups continue seamlessly.

## Success Criteria
- [ ] Reopening a prior session restores its datasets (incl. derived) and question history.
- [ ] A follow-up in a resumed session has access to prior-turn context.
