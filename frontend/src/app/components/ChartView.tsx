'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import type { ChartSpec, ResultRow } from '../lib/types'

// Renders the agent's auto-picked chart from chart_spec + result_table.
// Gracefully returns null when there is no spec or the referenced columns are absent.
export default function ChartView({
  spec,
  rows,
}: {
  spec: ChartSpec | null
  rows: ResultRow[]
}) {
  if (!spec || rows.length === 0) return null
  const hasCols = rows.every(r => spec.x in r && spec.y in r)
  if (!hasCols) return null

  // Coerce y to numbers for plotting; keep x as-is (category / value).
  const data = rows.map(r => ({
    ...r,
    [spec.y]: typeof r[spec.y] === 'number' ? r[spec.y] : Number(r[spec.y]),
  }))

  const color = '#2563eb'

  return (
    <div className="mt-4" data-testid="answer-chart">
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
        Chart · {spec.type}
      </div>
      <div className="h-64 w-full rounded-lg border border-gray-200 bg-white p-3">
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === 'line' ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey={spec.x} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey={spec.y} stroke={color} strokeWidth={2} dot={false} />
            </LineChart>
          ) : spec.type === 'scatter' ? (
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey={spec.x} name={spec.x} tick={{ fontSize: 12 }} />
              <YAxis dataKey={spec.y} name={spec.y} tick={{ fontSize: 12 }} />
              <ZAxis range={[60, 60]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={data} fill={color} />
            </ScatterChart>
          ) : (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey={spec.x} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey={spec.y} fill={color} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
