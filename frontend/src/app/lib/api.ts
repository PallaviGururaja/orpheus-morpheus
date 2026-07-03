// Same-origin API client. The static build is served under /app/, the API lives at
// the origin root (see spec/api.md), so all paths are absolute and origin-relative.
import type {
  AggregateRequest,
  AggregateResponse,
  AskResponse,
  BrowseResponse,
  Dashboard,
  DashboardSummary,
  DatasetResponse,
  QuerySummary,
  SessionDetail,
  SessionSummary,
  StepEvent,
  WidgetSpec,
} from './types'

export class ApiError extends Error {
  code: string
  status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
    this.name = 'ApiError'
  }
}

async function parse<T>(res: Response): Promise<T> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through to generic error below
  }
  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } } | null)?.detail
    throw new ApiError(
      detail?.code ?? 'error',
      detail?.message ?? `Request failed (${res.status})`,
      res.status,
    )
  }
  const data = (body as { data?: T } | null)?.data
  if (data === undefined || data === null) {
    throw new ApiError('bad_response', 'Malformed response from server.', res.status)
  }
  return data
}

export async function uploadDataset(
  file: File,
  sessionId: string | null,
): Promise<DatasetResponse> {
  const form = new FormData()
  form.append('file', file)
  if (sessionId) form.append('session_id', sessionId)
  const res = await fetch('/datasets', { method: 'POST', body: form })
  return parse<DatasetResponse>(res)
}

export async function ask(
  sessionId: string,
  datasetIds: string[],
  question: string,
): Promise<AskResponse> {
  const res = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, dataset_ids: datasetIds, question }),
  })
  return parse<AskResponse>(res)
}

export async function browseFiles(path: string | null): Promise<BrowseResponse> {
  const url = path ? `/local/browse?path=${encodeURIComponent(path)}` : '/local/browse'
  return parse<BrowseResponse>(await fetch(url))
}

export async function loadLocalDataset(
  path: string,
  sessionId: string | null,
): Promise<DatasetResponse> {
  const res = await fetch('/datasets/local', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, session_id: sessionId }),
  })
  return parse<DatasetResponse>(res)
}

export async function listQueries(sessionId: string): Promise<QuerySummary[]> {
  const res = await fetch(`/sessions/${sessionId}/queries`)
  const data = await parse<{ queries: QuerySummary[] }>(res)
  return data.queries ?? []
}

// --- Phase 2 ---

export interface StreamHandlers {
  onStep?: (event: StepEvent) => void
  onToken?: (text: string) => void
  onDone?: (data: AskResponse) => void
  onError?: (error: ApiError) => void
}

// Dispatch one SSE frame ("event: <type>\ndata: <json>") to the handlers.
function dispatchFrame(frame: string, handlers: StreamHandlers) {
  let eventType = 'message'
  const dataLines: string[] = []
  for (const rawLine of frame.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith(':')) continue // SSE comment / keep-alive
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }
  if (dataLines.length === 0) return
  let payload: unknown
  try {
    payload = JSON.parse(dataLines.join('\n'))
  } catch {
    return
  }
  switch (eventType) {
    case 'step':
      handlers.onStep?.(payload as StepEvent)
      break
    case 'token':
      handlers.onToken?.((payload as { text?: string }).text ?? '')
      break
    case 'done':
      handlers.onDone?.(payload as AskResponse)
      break
    case 'error': {
      const err = payload as { code?: string; message?: string }
      handlers.onError?.(
        new ApiError(err.code ?? 'INTERNAL', err.message ?? 'Analysis failed.', 500),
      )
      break
    }
  }
}

// Consume GET /ask/stream (text/event-stream) via fetch + ReadableStream so we
// control cancellation (AbortSignal) and can parse the named step/token/done/error
// events exactly per spec/api.md.
export async function streamAsk(
  sessionId: string,
  datasetIds: string[],
  question: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams()
  params.set('session_id', sessionId)
  for (const id of datasetIds) params.append('dataset_ids', id)
  params.set('question', question)

  const res = await fetch(`/ask/stream?${params.toString()}`, {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
    signal,
  })

  if (!res.ok || !res.body) {
    let code = 'error'
    let message = `Request failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: { code?: string; message?: string } }
      code = body?.detail?.code ?? code
      message = body?.detail?.message ?? message
    } catch {
      // non-JSON error body; keep generic message
    }
    handlers.onError?.(new ApiError(code, message, res.status))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      dispatchFrame(frame, handlers)
    }
  }
  buffer += decoder.decode()
  if (buffer.trim()) dispatchFrame(buffer, handlers)
}

export async function getFollowups(queryId: string): Promise<string[]> {
  const res = await fetch(`/queries/${queryId}/followups`)
  const data = await parse<{ followups: string[] }>(res)
  return data.followups ?? []
}

// Starter questions for a freshly loaded dataset (shown in the chat).
export async function getSuggestions(datasetId: string): Promise<string[]> {
  const res = await fetch(`/datasets/${datasetId}/suggestions`)
  const data = await parse<{ suggestions: string[] }>(res)
  return data.suggestions ?? []
}

export async function rerunQuery(queryId: string, code: string): Promise<AskResponse> {
  const res = await fetch(`/queries/${queryId}/rerun`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  return parse<AskResponse>(res)
}

// --- Phase 3 ---

// Download a query's persisted result_table as a CSV file. Streams the CSV bytes
// from GET /queries/{id}/export and triggers a browser download via an object URL.
export async function exportQueryCsv(queryId: string): Promise<void> {
  const res = await fetch(`/queries/${queryId}/export`)
  if (!res.ok) {
    let code = 'error'
    let message = `Request failed (${res.status})`
    try {
      const body = (await res.json()) as { detail?: { code?: string; message?: string } }
      code = body?.detail?.code ?? code
      message = body?.detail?.message ?? message
    } catch {
      // non-JSON error body; keep generic message
    }
    throw new ApiError(code, message, res.status)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `query-${queryId}.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

// --- Phase 3: dashboard builder (deterministic, no LLM) ---

// Aggregate one loaded dataset for a single widget (spec/api.md POST /dashboard/aggregate).
export async function aggregateWidget(
  req: AggregateRequest,
): Promise<AggregateResponse> {
  const res = await fetch('/dashboard/aggregate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  return parse<AggregateResponse>(res)
}

export async function saveDashboard(
  sessionId: string,
  name: string,
  widgets: WidgetSpec[],
): Promise<Dashboard> {
  const res = await fetch('/dashboards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, name, widgets }),
  })
  return parse<Dashboard>(res)
}

export async function updateDashboard(
  id: string,
  name: string,
  widgets: WidgetSpec[],
): Promise<Dashboard> {
  const res = await fetch(`/dashboards/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, widgets }),
  })
  return parse<Dashboard>(res)
}

export async function listDashboards(
  sessionId: string | null,
): Promise<DashboardSummary[]> {
  const url = sessionId
    ? `/dashboards?session_id=${encodeURIComponent(sessionId)}`
    : '/dashboards'
  const data = await parse<{ dashboards: DashboardSummary[] }>(await fetch(url))
  return data.dashboards ?? []
}

export async function getDashboard(id: string): Promise<Dashboard> {
  return parse<Dashboard>(await fetch(`/dashboards/${id}`))
}

export async function deleteDashboard(id: string): Promise<void> {
  await parse<{ deleted: boolean }>(
    await fetch(`/dashboards/${id}`, { method: 'DELETE' }),
  )
}

// --- Phase 3: session resume ---

export async function listSessions(): Promise<SessionSummary[]> {
  const data = await parse<{ sessions: SessionSummary[] }>(
    await fetch('/sessions'),
  )
  return data.sessions ?? []
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  return parse<SessionDetail>(await fetch(`/sessions/${sessionId}`))
}
