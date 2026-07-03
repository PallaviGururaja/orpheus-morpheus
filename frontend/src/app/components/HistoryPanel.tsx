'use client'

import type { QuerySummary } from '../lib/types'
import { StubButton } from './Stub'

// Right rail: read-only audit trail for the session (GET /sessions/{id}/queries).
export default function HistoryPanel({
  queries,
  onStub,
}: {
  queries: QuerySummary[]
  onStub: (message: string) => void
}) {
  return (
    <aside className="flex w-72 shrink-0 flex-col gap-4 border-l border-gray-200 bg-white p-4">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          History &amp; audit
        </h2>
        {queries.length === 0 ? (
          <p className="mt-2 text-xs text-gray-400">
            Your questions and the exact code run will appear here for review.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2" data-testid="history-list">
            {queries.map(q => (
              <li
                key={q.query_id}
                className="rounded-lg border border-gray-200 bg-gray-50 p-2.5 text-xs"
              >
                <p className="font-medium text-gray-800">{q.question}</p>
                <div className="mt-1 flex items-center justify-between text-[11px] text-gray-400">
                  <span>{formatTime(q.created_at)}</span>
                  {q.verified && <span className="text-green-600">✓ verified</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-auto">
        <StubButton label="Export CSV" phase="Phase 3" onStub={onStub} />
      </div>
    </aside>
  )
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}
