'use client'

import type { DatasetResponse } from '../lib/types'

// Renders the dataset profile returned by POST /datasets: columns + types,
// row/column counts, and visible data-quality flags (nulls / duplicates).
export default function ProfileCard({ dataset }: { dataset: DatasetResponse }) {
  const { profile } = dataset
  return (
    <section
      data-testid="profile-card"
      className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{dataset.name}</h2>
          <p className="text-xs text-gray-500">
            {dataset.row_count.toLocaleString()} rows · {dataset.column_count} columns
          </p>
        </div>
        {profile.duplicate_rows > 0 && (
          <span className="rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700">
            {profile.duplicate_rows.toLocaleString()} duplicate rows
          </span>
        )}
      </div>

      {profile.flags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {profile.flags.map((flag, i) => (
            <span
              key={i}
              className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800"
            >
              ⚠ {flag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500">
              <th className="py-1.5 pr-3 font-medium">Column</th>
              <th className="py-1.5 pr-3 font-medium">Type</th>
              <th className="py-1.5 pr-3 font-medium">Nulls</th>
              <th className="py-1.5 pr-3 font-medium">Distinct</th>
            </tr>
          </thead>
          <tbody>
            {profile.columns.map(col => {
              const nullPct = Math.round(col.null_pct * 100)
              return (
                <tr key={col.name} className="border-b border-gray-100 last:border-0">
                  <td className="py-1.5 pr-3 font-medium text-gray-900">{col.name}</td>
                  <td className="py-1.5 pr-3 text-gray-600">{col.dtype}</td>
                  <td className="py-1.5 pr-3">
                    {nullPct > 0 ? (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">
                        {nullPct}%
                      </span>
                    ) : (
                      <span className="text-gray-400">0%</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-3 text-gray-600">{col.distinct.toLocaleString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
