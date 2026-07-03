# Capability: Follow-up Suggestions (Phase 2)

## What It Does
After each answer, proposes 2-3 relevant follow-up questions the user can click to ask next.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question, answer_text, profile | mixed | AgentState | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| followups | string[] | UI chips + returned inline on `/ask` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Ollama | Generate suggestions | Non-fatal — return empty list, log |

## Business Rules
- Exactly 2-3 suggestions, grounded in the dataset's columns and the just-answered question.
- Non-critical: a failure here never fails the answer.

## Success Criteria
- [ ] Each answer returns 2-3 column-relevant follow-up questions.
- [ ] Clicking a suggestion submits it as the next question.
- [ ] A suggestion-generation failure still returns the main answer.
