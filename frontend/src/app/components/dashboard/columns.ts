import type { ColumnRole, PaletteColumn, Profile } from '../../lib/types'

// MIME-ish key for the native HTML5 drag payload. Kept custom so drops from
// outside the app are ignored.
export const DND_MIME = 'application/x-ebco-column'

// Classify a profile column from its dtype: numeric → measure, everything else
// (string / low-cardinality / dates) → dimension. Aligns with the backend
// palette typing described in spec/capabilities/dashboard-builder.md.
export function columnRole(dtype: string): ColumnRole {
  return /int|float|number|double|decimal|numeric|real|long/i.test(dtype)
    ? 'measure'
    : 'dimension'
}

export function paletteColumns(profile: Profile | null | undefined): PaletteColumn[] {
  if (!profile) return []
  return profile.columns.map(c => ({
    name: c.name,
    dtype: c.dtype,
    role: columnRole(c.dtype),
  }))
}

export interface DragPayload {
  name: string
  role: ColumnRole
}

export function readDragPayload(dt: DataTransfer | null): DragPayload | null {
  if (!dt) return null
  const raw = dt.getData(DND_MIME) || dt.getData('text/plain')
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as DragPayload
    if (parsed && typeof parsed.name === 'string' && parsed.role) return parsed
  } catch {
    // not our payload
  }
  return null
}
