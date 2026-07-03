// Types mirror the binding contract in spec/api.md.

export interface ProfileColumn {
  name: string
  dtype: string
  null_pct: number
  distinct: number
}

export interface Profile {
  columns: ProfileColumn[]
  duplicate_rows: number
  flags: string[]
}

export interface DatasetResponse {
  session_id: string
  dataset_id: string
  name: string
  row_count: number
  column_count: number
  profile: Profile
}

// Ask-tab charts (auto-picked by the agent).
export type ChartType = 'bar' | 'line' | 'scatter'

export interface ChartSpec {
  type: ChartType
  x: string
  y: string
}

// --- Phase 3: dashboard-builder chart types (superset of the ask-tab ones) ---
export type DashboardChartType = 'bar' | 'line' | 'scatter' | 'pie' | 'table'

// A row of the summary/result table — arbitrary column keys.
export type ResultRow = Record<string, string | number | boolean | null>

export interface AskResponse {
  query_id: string
  answer_text: string
  result_table: ResultRow[]
  chart_spec: ChartSpec | null
  code: string
  verified: boolean
  steps_used: number
  prompt_tokens: number
  completion_tokens: number
  elapsed_ms: number
}

export interface BrowseEntry {
  name: string
  path: string
  size?: number
}

export interface BrowseResponse {
  cwd: string
  parent: string | null
  shortcuts: { label: string; path: string }[]
  dirs: BrowseEntry[]
  files: BrowseEntry[]
}

export interface QuerySummary {
  query_id: string
  question: string
  created_at: string
  verified: boolean
}

// --- Phase 2: streaming step-trace events (spec/api.md `GET /ask/stream`) ---

export interface StepEvent {
  step: number
  total_estimate: number
  node: string
  elapsed_ms: number
}

export interface TokenEvent {
  text: string
}

export interface StreamErrorEvent {
  code: string
  message: string
}

export interface ApiError {
  code: string
  message: string
}

// --- Phase 3: dashboard builder (spec/api.md `POST /dashboard/aggregate`, `/dashboards`) ---

export type AggType = 'sum' | 'avg' | 'count' | 'min' | 'max'

// Client-side classification of a profile column, derived from its dtype.
export type ColumnRole = 'dimension' | 'measure'

export interface PaletteColumn {
  name: string
  dtype: string
  role: ColumnRole
  distinct?: number
}

// The persisted/spec portion of a widget (mirrors the `widgets` JSONB entry).
export interface WidgetLayout {
  x: number
  y: number
  w: number
  h: number
}

export interface WidgetSpec {
  id: string
  dimensions: string[]
  measure: string | null
  agg: AggType
  chart_type: DashboardChartType
  layout?: WidgetLayout
}

export interface AggregateRequest {
  dataset_id: string
  dimensions: string[]
  measure: string | null
  agg: AggType
  chart_type: DashboardChartType
}

export interface AggregateResponse {
  columns: string[]
  rows: ResultRow[]
  agg: AggType
  measure: string | null
  dimensions: string[]
  chart_type: DashboardChartType
  row_count: number
  truncated: boolean
}

export interface DashboardSummary {
  id: string
  session_id: string
  name: string
  created_at: string
}

export interface Dashboard extends DashboardSummary {
  widgets: WidgetSpec[]
}

// --- Phase 3: session resume (spec/api.md `GET /sessions`, `GET /sessions/{id}`) ---

export interface SessionSummary {
  id: string
  title: string | null
  dataset_count: number
  query_count: number
  created_at: string | null
  updated_at: string | null
}

export interface SessionDataset extends DatasetResponse {
  source_type: string
  is_derived: boolean
}

export interface SessionDetail {
  session: {
    id: string
    title: string | null
    created_at: string | null
    updated_at: string | null
  }
  datasets: SessionDataset[]
  queries: QuerySummary[]
}
