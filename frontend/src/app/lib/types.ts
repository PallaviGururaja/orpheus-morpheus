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

export type ChartType = 'bar' | 'line' | 'scatter'

export interface ChartSpec {
  type: ChartType
  x: string
  y: string
}

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

export interface QuerySummary {
  query_id: string
  question: string
  created_at: string
  verified: boolean
}

export interface ApiError {
  code: string
  message: string
}
