# Capabilities Index

> One file per capability. Each describes exactly one discrete thing the agent can do.

---

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Profile dataset on load | 1 | [profile-dataset.md](profile-dataset.md) |
| Analyze question (code-exec retry + verify) | 1 | [analyze-question.md](analyze-question.md) |
| Persist audit trail | 1 | [audit-trail.md](audit-trail.md) |
| Session conversation memory | 1 | [conversation-memory.md](conversation-memory.md) |
| Multi-dataset analysis (joins/unions) | 2 | [multi-dataset-analysis.md](multi-dataset-analysis.md) |
| Streaming step trace + timer | 2 | [streaming-step-trace.md](streaming-step-trace.md) |
| Follow-up suggestions | 2 | [followup-suggestions.md](followup-suggestions.md) |
| Editable code rerun | 2 | [editable-rerun.md](editable-rerun.md) |
| Drag-and-drop dashboard builder (headline) | 3 | [dashboard-builder.md](dashboard-builder.md) |
| CSV export | 3 | [csv-export.md](csv-export.md) |
| Excel ingestion | 3 | [excel-ingestion.md](excel-ingestion.md) |
| Cross-day session resume | 3 | [session-resume.md](session-resume.md) |
| DB-table connection (lowest priority; may defer to P4) | 3 | [db-table-connection.md](db-table-connection.md) |
| Large-data sampling (DuckDB) | 4 (deferred) | [large-data-sampling.md](large-data-sampling.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]`. The spec-writer creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews fit against the architecture and data model.
