# Capability: Editable Code Rerun (Phase 2)

## What It Does
Lets the user edit the agent's generated Python and rerun it, producing an updated answer and a new audit row.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| query_id | string | UI | yes |
| edited_code | string | UI code editor | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text / result_table / chart_spec | mixed | UI |
| new queries row | DB (`is_rerun=true`) | PostgreSQL |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Analysis engine | Execute edited code in restricted namespace | Error returned to UI (shown, not fatal) |
| PostgreSQL | Insert new audit row | 500 |

## Business Rules
- Edited code runs in the same restricted namespace as agent-generated code (no fs/net/os).
- The rerun creates a NEW audit row linked to the session; the original is preserved.

## Success Criteria
- [ ] Editing the code and rerunning returns a result reflecting the edit.
- [ ] A new `queries` row with `is_rerun=true` is persisted.
- [ ] A syntax error in edited code returns a clear error without crashing the app.
