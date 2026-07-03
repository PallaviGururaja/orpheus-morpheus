'use client'

import type { PaletteColumn } from '../../lib/types'
import ColumnChip from './ColumnChip'

// Left palette of draggable column chips grouped into DIMENSIONS and MEASURES,
// derived from the active dataset's profile.
export default function ColumnPalette({
  columns,
  datasetName,
}: {
  columns: PaletteColumn[]
  datasetName: string | null
}) {
  const dimensions = columns.filter(c => c.role === 'dimension')
  const measures = columns.filter(c => c.role === 'measure')

  return (
    <aside
      data-testid="column-palette"
      className="flex w-60 shrink-0 flex-col gap-4 overflow-y-auto border-r border-gray-200 bg-white p-4"
    >
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Columns
        </h3>
        <p className="mt-0.5 truncate text-[11px] text-gray-400" title={datasetName ?? ''}>
          {datasetName ?? 'No dataset loaded'}
        </p>
      </div>

      {columns.length === 0 ? (
        <p className="text-xs text-gray-400">
          Load a dataset on the Ask tab to see its columns here.
        </p>
      ) : (
        <>
          <Group
            title="Dimensions"
            hint="drag to group by"
            dotClass="bg-blue-500"
            columns={dimensions}
            empty="No categorical columns"
          />
          <Group
            title="Measures"
            hint="drag to aggregate"
            dotClass="bg-emerald-500"
            columns={measures}
            empty="No numeric columns"
          />
          <p className="mt-1 text-[11px] leading-relaxed text-gray-400">
            Drag a column onto a widget below. Dimensions group the data; measures
            are aggregated.
          </p>
        </>
      )}
    </aside>
  )
}

function Group({
  title,
  hint,
  dotClass,
  columns,
  empty,
}: {
  title: string
  hint: string
  dotClass: string
  columns: PaletteColumn[]
  empty: string
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5">
        <span className={'h-2 w-2 rounded-full ' + dotClass} />
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-gray-600">
          {title}
        </h4>
        <span className="text-[10px] text-gray-400">· {hint}</span>
      </div>
      {columns.length === 0 ? (
        <p className="text-[11px] text-gray-400">{empty}</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {columns.map(c => (
            <ColumnChip key={c.name} column={c} />
          ))}
        </div>
      )}
    </div>
  )
}
