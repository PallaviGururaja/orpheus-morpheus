// Same-origin API client. The static build is served under /app/, the API lives at
// the origin root (see spec/api.md), so all paths are absolute and origin-relative.
import type { AskResponse, BrowseResponse, DatasetResponse, QuerySummary } from './types'

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
