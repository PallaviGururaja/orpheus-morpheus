'use client'

import { useEffect, useState } from 'react'
import { ApiError, browseFiles } from '../lib/api'
import type { BrowseResponse } from '../lib/types'

// In-app file browser for local CSVs — a reliable alternative to the OS file
// dialog (which misbehaves on some Windows setups). Confined server-side to the
// user's home folder.
export default function FileBrowser({
  onPick,
  onClose,
}: {
  onPick: (path: string) => void
  onClose: () => void
}) {
  const [data, setData] = useState<BrowseResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function go(path: string | null) {
    setLoading(true)
    setError(null)
    try {
      setData(await browseFiles(path))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not read that folder.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Start in Downloads if it exists, else home.
    void (async () => {
      try {
        const home = await browseFiles(null)
        const downloads = home.shortcuts.find(s => s.label === 'Downloads')
        setData(downloads ? await browseFiles(downloads.path) : home)
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'Could not read your files.')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-900">Choose a CSV from your computer</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* shortcuts */}
        <div className="flex flex-wrap gap-2 border-b border-gray-100 px-4 py-2">
          {data?.shortcuts.map(s => (
            <button
              key={s.path}
              onClick={() => go(s.path)}
              className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-700"
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* current folder */}
        <div className="flex items-center gap-2 px-4 py-2 text-xs text-gray-500">
          <button
            disabled={!data?.parent}
            onClick={() => data?.parent && go(data.parent)}
            className="rounded border border-gray-200 px-2 py-1 font-medium text-gray-600 disabled:opacity-40 hover:bg-gray-50"
          >
            ↑ Up
          </button>
          <span className="truncate" title={data?.cwd}>
            {data?.cwd}
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {loading && <p className="px-3 py-4 text-sm text-gray-500">Loading…</p>}
          {error && (
            <p className="mx-2 my-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          )}
          {!loading && !error && data && (
            <ul className="flex flex-col">
              {data.dirs.map(d => (
                <li key={d.path}>
                  <button
                    onClick={() => go(d.path)}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
                  >
                    <span aria-hidden>📁</span>
                    <span className="truncate">{d.name}</span>
                  </button>
                </li>
              ))}
              {data.files.map(f => (
                <li key={f.path}>
                  <button
                    onClick={() => onPick(f.path)}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-gray-800 hover:bg-blue-50"
                  >
                    <span aria-hidden>📄</span>
                    <span className="truncate font-medium">{f.name}</span>
                    <span className="ml-auto shrink-0 text-xs text-gray-400">
                      {formatSize(f.size)}
                    </span>
                  </button>
                </li>
              ))}
              {data.dirs.length === 0 && data.files.length === 0 && (
                <p className="px-3 py-4 text-sm text-gray-400">
                  No sub-folders or CSV files here. Use the shortcuts above or “↑ Up”.
                </p>
              )}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

function formatSize(bytes?: number): string {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
