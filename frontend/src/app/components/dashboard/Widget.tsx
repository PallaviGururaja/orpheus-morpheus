'use client'

import { useCallback, useEffect, useState } from 'react'
import { aggregateWidget, ApiError } from '../../lib/api'
import type {
  AggregateResponse,
  AggType,
  DashboardChartType,
  WidgetSpec,
} from '../../lib/types'
import ChartView, { type ViewSpec } from '../ChartView'
import { readDragPayload } from './columns'

const AGGS: AggType[] = ['sum', 'avg', 'count', 'min', 'max']
const CHART_TYPES: DashboardChartType[] = ['bar', 'line', 'scatter', 'pie', 'table']

// One dashboard widget: dimension drop zone(s) + a measure drop zone, an
// aggregation selector, and a chart-type selector. A valid config auto-runs
// POST /dashboard/aggregate and renders through ChartView. No typing, no LLM.
export default function Widget({
  spec,
  datasetId,
  index,
  count,
  onChange,
  onRemove,
  onMove,
}: {
  spec: WidgetSpec
  datasetId: string | null
  index: number
  count: number
  onChange: (next: WidgetSpec) => void
  onRemove: () => void
  onMove: (dir: -1 | 1) => void
}) {
  const [result, setResult] = useState<AggregateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dropHint, setDropHint] = useState<'dimension' | 'measure' | null>(null)

  const runnable =
    !!datasetId && (spec.agg === 'count' || spec.measure !== null)

  // Fetch whenever the runnable config changes.
  useEffect(() => {
    if (!datasetId || !runnable) {
      setResult(null)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    aggregateWidget({
      dataset_id: datasetId,
      dimensions: spec.dimensions,
      measure: spec.measure,
      agg: spec.agg,
      chart_type: spec.chart_type,
    })
      .then(res => {
        if (!cancelled) setResult(res)
      })
      .catch(e => {
        if (cancelled) return
        setResult(null)
        setError(
          e instanceof ApiError
            ? e.message
            : 'Could not reach the server — is it running on this machine?',
        )
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // chart_type is intentionally included so a type switch re-renders; the
    // numbers are unchanged but the response echoes the new type.
  }, [datasetId, runnable, spec.dimensions, spec.measure, spec.agg, spec.chart_type])

  const handleDrop = useCallback(
    (zone: 'dimension' | 'measure', e: React.DragEvent) => {
      e.preventDefault()
      setDropHint(null)
      const payload = readDragPayload(e.dataTransfer)
      if (!payload) return
      if (zone === 'dimension') {
        if (payload.role !== 'dimension') {
          setError('Drop a dimension (categorical column) here to group by.')
          return
        }
        if (spec.dimensions.includes(payload.name)) return
        setError(null)
        onChange({ ...spec, dimensions: [...spec.dimensions, payload.name] })
      } else {
        if (payload.role !== 'measure') {
          setError('Pick a numeric measure.')
          return
        }
        setError(null)
        onChange({ ...spec, measure: payload.name })
      }
    },
    [spec, onChange],
  )

  const allowDrop = (zone: 'dimension' | 'measure') => (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setDropHint(zone)
  }

  const removeDimension = (name: string) =>
    onChange({ ...spec, dimensions: spec.dimensions.filter(d => d !== name) })

  const valueKey =
    result?.columns.find(c => !result.dimensions.includes(c)) ??
    result?.measure ??
    'value'
  const xKey = result?.dimensions[0] ?? valueKey

  const viewSpec: ViewSpec | null = result
    ? { type: result.chart_type, x: xKey, y: valueKey }
    : null

  const exportCsv = () => {
    if (!result || result.rows.length === 0) {
      setError('Nothing to export yet.')
      return
    }
    const cols = result.columns
    const escape = (v: unknown) => {
      const s = v === null || v === undefined ? '' : String(v)
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }
    const csv = [
      cols.join(','),
      ...result.rows.map(r => cols.map(c => escape(r[c])).join(',')),
    ].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `widget-${spec.id}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section
      data-testid="widget"
      data-widget-id={spec.id}
      className="flex flex-col rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      {/* Toolbar */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 text-xs text-gray-500">
          Agg
          <select
            data-testid="widget-agg"
            value={spec.agg}
            onChange={e => onChange({ ...spec, agg: e.target.value as AggType })}
            className="rounded border border-gray-300 bg-white px-1.5 py-1 text-xs text-gray-800"
          >
            {AGGS.map(a => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1 text-xs text-gray-500">
          Chart
          <select
            data-testid="widget-chart-type"
            value={spec.chart_type}
            onChange={e =>
              onChange({ ...spec, chart_type: e.target.value as DashboardChartType })
            }
            className="rounded border border-gray-300 bg-white px-1.5 py-1 text-xs text-gray-800"
          >
            {CHART_TYPES.map(t => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            aria-label="Move widget left"
            disabled={index === 0}
            onClick={() => onMove(-1)}
            className="rounded px-1.5 py-1 text-xs text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-30"
          >
            ←
          </button>
          <button
            type="button"
            aria-label="Move widget right"
            disabled={index === count - 1}
            onClick={() => onMove(1)}
            className="rounded px-1.5 py-1 text-xs text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-30"
          >
            →
          </button>
          <button
            type="button"
            data-testid="widget-export"
            onClick={exportCsv}
            className="rounded px-1.5 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
          >
            Export CSV
          </button>
          <button
            type="button"
            data-testid="widget-remove"
            aria-label="Remove widget"
            onClick={onRemove}
            className="rounded px-1.5 py-1 text-xs text-gray-400 hover:bg-red-50 hover:text-red-600"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Drop zones */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        <div
          data-testid="dimension-dropzone"
          onDragOver={allowDrop('dimension')}
          onDragLeave={() => setDropHint(null)}
          onDrop={e => handleDrop('dimension', e)}
          className={
            'min-h-[3rem] rounded-lg border-2 border-dashed p-2 text-xs transition ' +
            (dropHint === 'dimension'
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-200 bg-gray-50')
          }
        >
          <div className="mb-1 font-medium uppercase tracking-wide text-blue-500">
            Dimensions
          </div>
          {spec.dimensions.length === 0 ? (
            <span className="text-gray-400">Drop dimension chips here</span>
          ) : (
            <div className="flex flex-wrap gap-1">
              {spec.dimensions.map(d => (
                <span
                  key={d}
                  data-testid="widget-dimension"
                  className="flex items-center gap-1 rounded bg-blue-100 px-1.5 py-0.5 font-medium text-blue-800"
                >
                  {d}
                  <button
                    type="button"
                    aria-label={`Remove dimension ${d}`}
                    onClick={() => removeDimension(d)}
                    className="text-blue-500 hover:text-blue-800"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div
          data-testid="measure-dropzone"
          onDragOver={allowDrop('measure')}
          onDragLeave={() => setDropHint(null)}
          onDrop={e => handleDrop('measure', e)}
          className={
            'min-h-[3rem] rounded-lg border-2 border-dashed p-2 text-xs transition ' +
            (dropHint === 'measure'
              ? 'border-emerald-400 bg-emerald-50'
              : 'border-gray-200 bg-gray-50')
          }
        >
          <div className="mb-1 font-medium uppercase tracking-wide text-emerald-600">
            Measure
          </div>
          {spec.measure ? (
            <span
              data-testid="widget-measure"
              className="flex w-fit items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-800"
            >
              {spec.measure}
              <button
                type="button"
                aria-label="Remove measure"
                onClick={() => onChange({ ...spec, measure: null })}
                className="text-emerald-600 hover:text-emerald-900"
              >
                ×
              </button>
            </span>
          ) : spec.agg === 'count' ? (
            <span className="text-gray-400">Not needed for count</span>
          ) : (
            <span className="text-gray-400">Drop a measure chip here</span>
          )}
        </div>
      </div>

      {/* Result */}
      <div className="min-h-[4rem]">
        {error && (
          <p
            data-testid="widget-error"
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
          >
            {error}
          </p>
        )}
        {loading && !error && (
          <p className="px-1 py-2 text-xs text-gray-400">Aggregating…</p>
        )}
        {!runnable && !error && !loading && (
          <p
            data-testid="widget-empty"
            className="px-1 py-2 text-xs text-gray-400"
          >
            Drop a measure (or pick <span className="font-medium">count</span>) to
            build this chart.
          </p>
        )}
        {result && viewSpec && !loading && !error && (
          <ChartView spec={viewSpec} rows={result.rows} columns={result.columns} />
        )}
        {result && result.truncated && (
          <p className="mt-1 text-[11px] text-amber-600">
            Showing the first {result.rows.length} rows (result was truncated).
          </p>
        )}
      </div>
    </section>
  )
}
