'use client'

import { useEffect, useRef, useState } from 'react'

// Drag/drop or pick a single CSV. Emits the chosen File to the parent, which
// owns the POST /datasets call and the loading/error state.
export default function UploadPanel({
  onFile,
  loading,
  error,
  hasDataset,
  registerOpen,
  onBrowse,
}: {
  onFile: (file: File) => void
  loading: boolean
  error: string | null
  hasDataset: boolean
  // Lets other UI (e.g. the sidebar "Add dataset" button) open this picker.
  registerOpen?: (open: () => void) => void
  // Opens the in-app file browser (reliable alternative to the OS dialog).
  onBrowse: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  // Expose an imperative "open the file dialog" to the parent.
  useEffect(() => {
    registerOpen?.(() => inputRef.current?.click())
  }, [registerOpen])

  function pick(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    // Phase 1 is CSV-only. The picker no longer filters by extension (so your
    // downloaded file always shows up), so validate here with a clear message.
    if (!/\.csv$/i.test(file.name)) {
      setLocalError(
        `“${file.name}” isn’t a CSV. Phase 1 supports CSV files only — ` +
          `if it’s an Excel file, re-save it as CSV (File → Save As → CSV) and upload that.`,
      )
      return
    }
    setLocalError(null)
    onFile(file)
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div
        onDragOver={e => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault()
          setDragging(false)
          if (!loading) pick(e.dataTransfer.files)
        }}
        className={
          'flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 text-center transition ' +
          (dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 bg-gray-50')
        }
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          data-testid="file-input"
          onChange={e => pick(e.target.files)}
          disabled={loading}
        />
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-gray-600" data-testid="upload-loading">
            <Spinner />
            Profiling dataset…
          </div>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-700">
              {hasDataset ? 'Replace CSV' : 'Drop a CSV here, or'}
            </p>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                onClick={onBrowse}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Browse my computer
              </button>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Use system dialog
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-400">
              CSV only in Phase 1 · nothing leaves your machine
            </p>
          </>
        )}
      </div>

      {(localError || error) && (
        <div
          role="alert"
          data-testid="upload-error"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {localError || error}
        </div>
      )}
    </section>
  )
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-blue-600 motion-reduce:animate-none"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}
