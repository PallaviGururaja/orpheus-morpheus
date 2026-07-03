'use client'

import { useCallback, useState } from 'react'
import { getDashboard, saveDashboard, updateDashboard, ApiError } from '../../lib/api'
import type { DatasetResponse, WidgetSpec } from '../../lib/types'
import ColumnPalette from './ColumnPalette'
import DashboardToolbar from './DashboardToolbar'
import Widget from './Widget'
import { paletteColumns } from './columns'

let widgetSeq = 0
function newWidget(): WidgetSpec {
  widgetSeq += 1
  return {
    id: `w${Date.now().toString(36)}-${widgetSeq}`,
    dimensions: [],
    measure: null,
    agg: 'sum',
    chart_type: 'bar',
  }
}

// The Dashboard tab: a palette of draggable column chips + a grid of aggregation
// widgets. Deterministic, no LLM. Save / reload dashboards via the CRUD endpoints.
export default function DashboardView({
  activeDataset,
  sessionId,
}: {
  activeDataset: DatasetResponse | null
  sessionId: string | null
}) {
  const [widgets, setWidgets] = useState<WidgetSpec[]>([])
  const [name, setName] = useState('')
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [reloadSignal, setReloadSignal] = useState(0)

  const columns = paletteColumns(activeDataset?.profile)
  const datasetId = activeDataset?.dataset_id ?? null

  const addWidget = useCallback(() => {
    setWidgets(prev => [...prev, newWidget()])
  }, [])

  const updateWidget = useCallback((next: WidgetSpec) => {
    setWidgets(prev => prev.map(w => (w.id === next.id ? next : w)))
  }, [])

  const removeWidget = useCallback((id: string) => {
    setWidgets(prev => prev.filter(w => w.id !== id))
  }, [])

  const moveWidget = useCallback((index: number, dir: -1 | 1) => {
    setWidgets(prev => {
      const target = index + dir
      if (target < 0 || target >= prev.length) return prev
      const next = [...prev]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }, [])

  const startNew = useCallback(() => {
    setWidgets([])
    setName('')
    setCurrentId(null)
    setSaveError(null)
  }, [])

  const handleSave = useCallback(async () => {
    if (!sessionId) {
      setSaveError('Load a dataset first.')
      return
    }
    const dashName = name.trim() || 'Untitled dashboard'
    setSaving(true)
    setSaveError(null)
    try {
      const saved = currentId
        ? await updateDashboard(currentId, dashName, widgets)
        : await saveDashboard(sessionId, dashName, widgets)
      setCurrentId(saved.id)
      setName(saved.name)
      setReloadSignal(s => s + 1)
    } catch (e) {
      setSaveError(
        e instanceof ApiError ? e.message : 'Could not save the dashboard.',
      )
    } finally {
      setSaving(false)
    }
  }, [sessionId, name, currentId, widgets])

  const handleReload = useCallback(async (id: string) => {
    setSaveError(null)
    try {
      const dash = await getDashboard(id)
      setWidgets(dash.widgets ?? [])
      setName(dash.name)
      setCurrentId(dash.id)
    } catch (e) {
      setSaveError(
        e instanceof ApiError ? e.message : 'Could not load that dashboard.',
      )
    }
  }, [])

  return (
    <div className="flex min-h-0 flex-1" data-testid="dashboard-view">
      <ColumnPalette columns={columns} datasetName={activeDataset?.name ?? null} />

      <div className="flex min-h-0 flex-1 flex-col">
        <DashboardToolbar
          name={name}
          onNameChange={setName}
          sessionId={sessionId}
          currentId={currentId}
          saving={saving}
          saveError={saveError}
          onAddWidget={addWidget}
          onSave={handleSave}
          onReload={handleReload}
          onNew={startNew}
          reloadSignal={reloadSignal}
        />

        <div className="flex-1 overflow-y-auto bg-gray-50 p-4">
          {!activeDataset ? (
            <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
              <p className="text-sm font-medium text-gray-700">No dataset loaded</p>
              <p className="mt-1 text-sm text-gray-400">
                Load a dataset on the Ask tab, then drag its columns into widgets here.
              </p>
            </div>
          ) : widgets.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
              <p className="text-sm font-medium text-gray-700">Build your dashboard</p>
              <p className="mt-1 text-sm text-gray-400">
                Click <span className="font-medium">+ Add widget</span>, then drag a
                dimension and a measure into it. No typing, no waiting on the model.
              </p>
              <button
                type="button"
                onClick={addWidget}
                data-testid="add-widget-empty"
                className="mt-4 rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                + Add your first widget
              </button>
            </div>
          ) : (
            <div
              data-testid="widget-grid"
              className="grid grid-cols-1 gap-4 xl:grid-cols-2"
            >
              {widgets.map((w, i) => (
                <Widget
                  key={w.id}
                  spec={w}
                  datasetId={datasetId}
                  index={i}
                  count={widgets.length}
                  onChange={updateWidget}
                  onRemove={() => removeWidget(w.id)}
                  onMove={dir => moveWidget(i, dir)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
