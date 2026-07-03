// Same-origin API client. The static build is served under /app/, the API lives at
// the origin root (see spec/api.md), so all paths are absolute and origin-relative.
import type {
  AskResponse,
  BrowseResponse,
  DatasetResponse,
  QuerySummary,
  StepEvent,
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

export async function rerunQuery(queryId: string, code: string): Promise<AskResponse> {
  const res = await fetch(`/queries/${queryId}/rerun`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  return parse<AskResponse>(res)
}
