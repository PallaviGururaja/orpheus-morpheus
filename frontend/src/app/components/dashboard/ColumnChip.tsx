'use client'

import type { PaletteColumn } from '../../lib/types'
import { DND_MIME } from './columns'

// A draggable column chip. Dimensions and measures are visually distinguished.
export default function ColumnChip({ column }: { column: PaletteColumn }) {
  const isMeasure = column.role === 'measure'
  return (
    <div
      draggable
      data-testid="column-chip"
      data-role={column.role}
      data-column={column.name}
      onDragStart={e => {
        const payload = JSON.stringify({ name: column.name, role: column.role })
        e.dataTransfer.setData(DND_MIME, payload)
        e.dataTransfer.setData('text/plain', payload)
        e.dataTransfer.effectAllowed = 'copy'
      }}
      title={`${column.name} · ${column.dtype} · ${column.role}`}
      className={
        'flex cursor-grab items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium shadow-sm transition active:cursor-grabbing ' +
        (isMeasure
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
          : 'border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100')
      }
    >
      <span
        className={
          'h-2 w-2 shrink-0 rounded-full ' +
          (isMeasure ? 'bg-emerald-500' : 'bg-blue-500')
        }
      />
      <span className="truncate">{column.name}</span>
    </div>
  )
}
