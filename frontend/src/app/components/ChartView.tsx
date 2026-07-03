'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import type { DashboardChartType, ResultRow } from '../lib/types'

// A chart spec broad enough for both the ask tab (bar/line/scatter) and the
// dashboard builder (adds pie + table). ChartSpec is assignable to this.
export interface ViewSpec {
  type: DashboardChartType
  x: string
  y: string
}

// Palette used for pie slices / multi-category fills.
const PALETTE = [
  '#2563eb',
  '#16a34a',
  '#f59e0b',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
]

// Renders a chart from a spec + rows. Supports bar/line/scatter (ask + dashboard)
// plus pie/table (dashboard). `columns` is used for the table renderer; when
// omitted it falls back to the keys of the first row.
// Gracefully returns null when there is no spec or the referenced columns are absent.
export default function ChartView({
  spec,
  rows,
  columns,
}: {
  spec: ViewSpec | null
  rows: ResultRow[]
  columns?: string[]
}) {
  if (!spec || rows.length === 0) return null

  // Table renders every column — it does not need x/y to be present.
  if (spec.type === 'table') {
    const cols = columns ?? Object.keys(rows[0])
    return (
      <div className="mt-4" data-testid="answer-chart">
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
          Chart · table
        </div>
        <div
          className="max-h-64 w-full overflow-auto rounded-lg border border-gray-200 bg-white"
          data-testid="chart-table"
        >
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-gray-50">
              <tr className="border-b border-gray-200 text-gray-500">
                {cols.map(c => (
                  <th key={c} className="px-3 py-1.5 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-gray-100 last:border-0">
                  {cols.map(c => (
                    <td key={c} className="px-3 py-1.5 text-gray-800">
                      {formatCell(r[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const hasCols = rows.every(r => spec.x in r && spec.y in r)
  if (!hasCols) return null

  // Coerce y to numbers for plotting; keep x as-is (category / value).
  const data = rows.map(r => ({
    ...r,
    [spec.y]: typeof r[spec.y] === 'number' ? r[spec.y] : Number(r[spec.y]),
  }))

  const color = PALETTE[0]

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
          ) : spec.type === 'pie' ? (
            <PieChart>
              <Tooltip />
              <Legend />
              <Pie
                data={data}
                dataKey={spec.y}
                nameKey={spec.x}
                cx="50%"
                cy="50%"
                outerRadius={80}
                label
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
            </PieChart>
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

function formatCell(value: string | number | boolean | null): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}
