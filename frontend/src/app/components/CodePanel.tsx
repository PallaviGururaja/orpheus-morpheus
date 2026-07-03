'use client'

import { useEffect, useState } from 'react'
import { ApiError } from '../lib/api'

// Collapsible view of the exact Python the agent ran. Phase 2: now EDITABLE with a
// Rerun button that POSTs to /queries/{id}/rerun and shows the new result. A sandbox
// error from the edited code is shown inline so the user can fix and rerun.
export default function CodePanel({
  code,
  onRerun,
}: {
  code: string
  // Runs the edited code; resolves when the new result has been applied, rejects
  // (ApiError) so the sandbox error can be shown inline.
  onRerun: (code: string) => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(code)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // When a new answer (or a rerun result) arrives, resync the editor to its code.
  useEffect(() => {
    setDraft(code)
    setError(null)
  }, [code])

  const dirty = draft !== code

  async function rerun() {
    const next = draft.trim()
    if (!next || running) return
    setRunning(true)
    setError(null)
    try {
      await onRerun(next)
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : 'Could not reach the server — is it running on this machine?',
      )
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        data-testid="code-toggle"
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
      >
        <span>{open ? '▾' : '▸'} Generated Python</span>
        <span className="text-xs font-normal text-gray-400">editable · rerun</span>
      </button>

      {open && (
        <div className="border-t border-gray-200 p-3">
          <textarea
            data-testid="code-editor"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            spellCheck={false}
            rows={Math.min(16, Math.max(4, draft.split('\n').length + 1))}
            className="w-full resize-y rounded bg-gray-900 p-3 font-mono text-xs leading-relaxed text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />

          {error && (
            <div
              role="alert"
              data-testid="rerun-error"
              className="mt-2 overflow-x-auto whitespace-pre-wrap rounded border border-red-200 bg-red-50 p-2.5 font-mono text-xs text-red-700"
            >
              {error}
            </div>
          )}

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={rerun}
              disabled={running || !draft.trim()}
              data-testid="rerun-button"
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {running && (
                <svg
                  className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                  />
                </svg>
              )}
              {running ? 'Running…' : 'Rerun'}
            </button>
            {dirty && !running && (
              <button
                type="button"
                onClick={() => {
                  setDraft(code)
                  setError(null)
                }}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Reset to generated
              </button>
            )}
            {dirty && (
              <span className="text-xs text-amber-600">edited — not yet run</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
