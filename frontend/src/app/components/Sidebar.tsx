'use client'

import type { DatasetResponse } from '../lib/types'
import SessionPicker from './SessionPicker'
import { StubButton } from './Stub'

// Left rail (Phase 2, real): the full list of datasets loaded in the session, each
// selectable (its id flows into /ask) and removable. "Add dataset" opens the real
// FileBrowser. DB-connect / Excel / session-switch remain labelled Phase-3 stubs.
export default function Sidebar({
  datasets,
  selectedIds,
  onToggle,
  onRemove,
  onAddDataset,
  onStub,
}: {
  datasets: DatasetResponse[]
  selectedIds: string[]
  onToggle: (datasetId: string) => void
  onRemove: (datasetId: string) => void
  onAddDataset: () => void
  onStub: (message: string) => void
}) {
  return (
    <aside className="flex w-64 shrink-0 flex-col gap-4 overflow-y-auto border-r border-gray-200 bg-white p-4">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Datasets
          </h2>
          {datasets.length > 0 && (
            <span className="text-[11px] text-gray-400">{datasets.length} loaded</span>
          )}
        </div>

        {datasets.length === 0 ? (
          <p className="text-xs text-gray-400">No datasets loaded yet.</p>
        ) : (
          <ul data-testid="dataset-list" className="flex flex-col gap-2">
            {datasets.map(ds => {
              const selected = selectedIds.includes(ds.dataset_id)
              return (
                <li
                  key={ds.dataset_id}
                  data-testid="dataset-item"
                  className={
                    'group flex items-start gap-2 rounded-lg border p-2.5 ' +
                    (selected
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-gray-200 bg-gray-50')
                  }
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggle(ds.dataset_id)}
                    aria-label={`Include ${ds.name} in analysis`}
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-blue-600"
                  />
                  <div className="min-w-0 flex-1">
                    <p
                      className="truncate text-sm font-medium text-gray-900"
                      title={ds.name}
                    >
                      {ds.name}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {ds.row_count.toLocaleString()} rows · {ds.column_count} cols
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemove(ds.dataset_id)}
                    aria-label={`Remove ${ds.name}`}
                    data-testid="remove-dataset"
                    className="shrink-0 rounded px-1 text-gray-400 hover:bg-gray-200 hover:text-red-600"
                  >
                    ×
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Sources
        </h2>
        <div className="flex flex-col gap-2">
          <button
            type="button"
            onClick={onAddDataset}
            data-testid="add-dataset"
            className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-left text-sm font-medium text-blue-700 hover:bg-blue-100"
          >
            {datasets.length > 0 ? 'Add dataset' : 'Add dataset'}
          </button>
          <StubButton label="Connect DB" phase="Phase 3" onStub={onStub} />
          <StubButton label="Upload Excel" phase="Phase 3" onStub={onStub} />
        </div>
      </div>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Sessions
        </h2>
        {/* Phase 3 (real): cross-day session resume. Replaces the old stub. */}
        <SessionPicker />
      </div>
    </aside>
  )
}
