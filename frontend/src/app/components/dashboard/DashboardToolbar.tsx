'use client'

import { useEffect, useState } from 'react'
import { deleteDashboard, listDashboards } from '../../lib/api'
import type { DashboardSummary } from '../../lib/types'

// Top bar of the dashboard builder: name input, Add-widget, Save/Update, and a
// picker of saved dashboards (reload / delete).
export default function DashboardToolbar({
  name,
  onNameChange,
  sessionId,
  currentId,
  saving,
  saveError,
  onAddWidget,
  onSave,
  onReload,
  onNew,
  reloadSignal,
}: {
  name: string
  onNameChange: (name: string) => void
  sessionId: string | null
  currentId: string | null
  saving: boolean
  saveError: string | null
  onAddWidget: () => void
  onSave: () => void
  onReload: (id: string) => void
  onNew: () => void
  reloadSignal: number
}) {
  const [saved, setSaved] = useState<DashboardSummary[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (!sessionId) {
      setSaved([])
      return
    }
    listDashboards(sessionId)
      .then(list => {
        if (!cancelled) setSaved(list)
      })
      .catch(() => {
        if (!cancelled) setSaved([])
      })
    return () => {
      cancelled = true
    }
  }, [sessionId, reloadSignal])

  const handleDelete = async (id: string) => {
    try {
      await deleteDashboard(id)
      setSaved(prev => prev.filter(d => d.id !== id))
      if (id === currentId) onNew()
    } catch {
      // non-fatal; leave the list as-is
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-gray-200 bg-white px-4 py-2.5">
      <input
        data-testid="dashboard-name"
        value={name}
        onChange={e => onNameChange(e.target.value)}
        placeholder="Untitled dashboard"
        className="min-w-[12rem] flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-400 focus:outline-none"
      />

      <button
        type="button"
        data-testid="add-widget"
        onClick={onAddWidget}
        className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-100"
      >
        + Add widget
      </button>

      <button
        type="button"
        data-testid="save-dashboard"
        onClick={onSave}
        disabled={saving || !sessionId}
        className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40"
      >
        {saving ? 'Saving…' : currentId ? 'Update' : 'Save'}
      </button>

      <div className="relative">
        <button
          type="button"
          data-testid="dashboard-picker-toggle"
          onClick={() => setPickerOpen(o => !o)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Saved ({saved.length}) ▾
        </button>
        {pickerOpen && (
          <div
            data-testid="dashboard-picker"
            className="absolute right-0 z-20 mt-1 max-h-72 w-64 overflow-y-auto rounded-lg border border-gray-200 bg-white p-1 shadow-lg"
          >
            <button
              type="button"
              onClick={() => {
                onNew()
                setPickerOpen(false)
              }}
              className="w-full rounded px-2 py-1.5 text-left text-sm text-gray-600 hover:bg-gray-100"
            >
              + New dashboard
            </button>
            {saved.length === 0 ? (
              <p className="px-2 py-2 text-xs text-gray-400">No saved dashboards yet.</p>
            ) : (
              saved.map(d => (
                <div
                  key={d.id}
                  data-testid="saved-dashboard"
                  className="group flex items-center gap-1 rounded hover:bg-gray-100"
                >
                  <button
                    type="button"
                    onClick={() => {
                      onReload(d.id)
                      setPickerOpen(false)
                    }}
                    className="min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm text-gray-800"
                    title={d.name}
                  >
                    {d.name}
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${d.name}`}
                    onClick={() => handleDelete(d.id)}
                    className="shrink-0 px-2 py-1 text-xs text-gray-400 hover:text-red-600"
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {saveError && (
        <span data-testid="save-error" role="alert" className="text-xs text-red-600">
          {saveError}
        </span>
      )}
    </div>
  )
}
