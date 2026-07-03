'use client'

import type { DatasetResponse } from '../lib/types'
import { StubButton } from './Stub'

// Left rail: the one real loaded dataset (Phase 1) + labelled stubs for
// multi-dataset / DB-connect / session-switch (Phase 2/3).
export default function Sidebar({
  dataset,
  onStub,
}: {
  dataset: DatasetResponse | null
  onStub: (message: string) => void
}) {
  return (
    <aside className="flex w-64 shrink-0 flex-col gap-4 border-r border-gray-200 bg-white p-4">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Dataset</h2>
        {dataset ? (
          <div className="mt-2 rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="truncate text-sm font-medium text-gray-900" title={dataset.name}>
              {dataset.name}
            </p>
            <p className="mt-0.5 text-xs text-gray-500">
              {dataset.row_count.toLocaleString()} rows · {dataset.column_count} cols
            </p>
          </div>
        ) : (
          <p className="mt-2 text-xs text-gray-400">No dataset loaded yet.</p>
        )}
      </div>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Sources</h2>
        <div className="flex flex-col gap-2">
          <StubButton label="Add dataset" phase="Phase 2" onStub={onStub} />
          <StubButton label="Connect DB" phase="Phase 3" onStub={onStub} />
          <StubButton label="Upload Excel" phase="Phase 3" onStub={onStub} />
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Sessions</h2>
        <StubButton label="Switch session" phase="Phase 3" onStub={onStub} />
      </div>
    </aside>
  )
}
