'use client'

import { useCallback, useEffect, useState } from 'react'
import { ApiError, getSession, listSessions } from '../lib/api'
import type { SessionDetail, SessionSummary } from '../lib/types'

// The event the picker emits once a prior session is rehydrated. The workbench
// (page.tsx) can listen for `ebco:session-restore` and repopulate its datasets +
// history from the detail payload — the picker itself owns only the fetch/select
// flow so it stays self-contained and free of parent-state coupling.
export const SESSION_RESTORE_EVENT = 'ebco:session-restore'

export function emitSessionRestore(detail: SessionDetail) {
  window.dispatchEvent(new CustomEvent(SESSION_RESTORE_EVENT, { detail }))
}

// Cross-day session resume (Phase 3). Lists prior sessions with their dataset /
// query counts; selecting one loads GET /sessions/{id} and restores the workbench.
// Replaces the old "Switch session" stub in the sidebar.
export default function SessionPicker({
  onRestore,
}: {
  // Optional hook for a parent that wants the payload directly; when omitted the
  // picker still broadcasts SESSION_RESTORE_EVENT on window.
  onRestore?: (detail: SessionDetail) => void
}) {
  const [open, setOpen] = useState(false)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingId, setLoadingId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSessions(await listSessions())
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : 'Could not reach the server — is it running on this machine?',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) void refresh()
  }, [open, refresh])

  const handlePick = useCallback(
    async (id: string) => {
      setLoadingId(id)
      setError(null)
      try {
        const detail = await getSession(id)
        emitSessionRestore(detail)
        onRestore?.(detail)
        setOpen(false)
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not load that session.')
      } finally {
        setLoadingId(null)
      }
    },
    [onRestore],
  )

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-testid="open-session-picker"
        className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-left text-sm font-medium text-gray-700 hover:bg-gray-100"
      >
        Switch session
      </button>

      {open && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Resume a prior session"
          data-testid="session-picker-modal"
          onClick={() => setOpen(false)}
        >
          <div
            className="flex max-h-[70vh] w-full max-w-md flex-col overflow-hidden rounded-xl bg-white shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-gray-900">
                Resume a session
              </h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="rounded px-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
              >
                ×
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              {loading && (
                <p className="py-8 text-center text-sm text-gray-400">
                  Loading sessions…
                </p>
              )}

              {!loading && error && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
                >
                  {error}
                </div>
              )}

              {!loading && !error && sessions.length === 0 && (
                <p className="py-8 text-center text-sm text-gray-400">
                  No prior sessions yet. Load a dataset to start one.
                </p>
              )}

              {!loading && !error && sessions.length > 0 && (
                <ul data-testid="session-list" className="flex flex-col gap-2">
                  {sessions.map(s => (
                    <li key={s.id}>
                      <button
                        type="button"
                        onClick={() => handlePick(s.id)}
                        disabled={loadingId !== null}
                        data-testid="session-item"
                        className="flex w-full items-center justify-between gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-left hover:border-blue-300 hover:bg-blue-50 disabled:opacity-50"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-gray-900">
                            {s.title || 'Untitled session'}
                          </p>
                          <p className="mt-0.5 text-xs text-gray-500">
                            {s.dataset_count} dataset
                            {s.dataset_count === 1 ? '' : 's'} · {s.query_count}{' '}
                            quer{s.query_count === 1 ? 'y' : 'ies'}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-blue-600">
                          {loadingId === s.id ? 'Loading…' : 'Resume'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
