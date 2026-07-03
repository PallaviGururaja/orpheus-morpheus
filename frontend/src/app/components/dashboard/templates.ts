import type { PaletteColumn, WidgetSpec } from '../../lib/types'

// Predefined ("one-click") dashboards, auto-built from the loaded dataset's
// columns — no dragging required. Deterministic; each widget is a normal
// WidgetSpec that the aggregation endpoint renders.

export interface DashboardTemplate {
  key: string
  name: string
  description: string
  // Build widgets from the available columns; returns [] if the data doesn't fit.
  build: (cols: PaletteColumn[]) => WidgetSpec[]
}

let seq = 0
function widget(spec: Omit<WidgetSpec, 'id'>): WidgetSpec {
  seq += 1
  return { id: `tpl${Date.now().toString(36)}-${seq}`, ...spec }
}

const isDateLike = (x: PaletteColumn) =>
  /date|time|day|month|year|period|timestamp/i.test(x.name)

const measures = (c: PaletteColumn[]) => c.filter(x => x.role === 'measure')

// Good grouping columns: categorical, NOT date-like, and low-cardinality
// (grouping by a 10k-distinct column produces an unreadable chart). Ordered
// fewest-distinct first so the best category leads.
const groupDims = (c: PaletteColumn[]) =>
  c
    .filter(
      x =>
        x.role === 'dimension' &&
        !isDateLike(x) &&
        (x.distinct == null || x.distinct <= 50),
    )
    .sort((a, b) => (a.distinct ?? 999) - (b.distinct ?? 999))

// Heuristic: a column that looks like a date/time dimension (for trend lines).
const dateDim = (c: PaletteColumn[]) => c.find(x => x.role === 'dimension' && isDateLike(x))

export const TEMPLATES: DashboardTemplate[] = [
  {
    key: 'overview',
    name: 'Overview',
    description: 'Totals and averages of your first measure across your main category.',
    build: cols => {
      const d = groupDims(cols)
      const m = measures(cols)
      if (!d.length || !m.length) return []
      const dim = d[0].name
      const out: WidgetSpec[] = [
        widget({ dimensions: [dim], measure: m[0].name, agg: 'sum', chart_type: 'bar' }),
        widget({ dimensions: [dim], measure: m[0].name, agg: 'avg', chart_type: 'bar' }),
        widget({ dimensions: [dim], measure: null, agg: 'count', chart_type: 'pie' }),
      ]
      if (m[1]) {
        out.push(
          widget({ dimensions: [dim], measure: m[1].name, agg: 'sum', chart_type: 'bar' }),
        )
      }
      return out
    },
  },
  {
    key: 'trend',
    name: 'Trends over time',
    description: 'Your measures plotted over the date column.',
    build: cols => {
      const dateCol = dateDim(cols)
      const m = measures(cols)
      if (!dateCol || !m.length) return []
      return m
        .slice(0, 3)
        .map(measure =>
          widget({
            dimensions: [dateCol.name],
            measure: measure.name,
            agg: 'avg',
            chart_type: 'line',
          }),
        )
    },
  },
  {
    key: 'breakdown',
    name: 'Category breakdown',
    description: 'Row counts and totals for each of your categories.',
    build: cols => {
      const d = groupDims(cols)
      const m = measures(cols)
      if (!d.length) return []
      const out: WidgetSpec[] = d
        .slice(0, 3)
        .map(dim =>
          widget({ dimensions: [dim.name], measure: null, agg: 'count', chart_type: 'bar' }),
        )
      if (m[0] && d[0]) {
        out.push(
          widget({
            dimensions: [d[0].name],
            measure: m[0].name,
            agg: 'sum',
            chart_type: 'table',
          }),
        )
      }
      return out
    },
  },
]

// Which templates are applicable to the current columns (produce ≥1 widget).
export function availableTemplates(cols: PaletteColumn[]): DashboardTemplate[] {
  return TEMPLATES.filter(t => t.build(cols).length > 0)
}
