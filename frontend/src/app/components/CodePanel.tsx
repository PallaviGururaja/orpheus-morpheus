'use client'

import { useState } from 'react'
import { StubButton } from './Stub'

// Collapsed-by-default, read-only view of the exact Python the agent ran.
// The "Edit & rerun" control is a labelled Phase-2 stub.
export default function CodePanel({
  code,
  onStub,
}: {
  code: string
  onStub: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
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
        <span className="text-xs font-normal text-gray-400">read-only</span>
      </button>
      {open && (
        <div className="border-t border-gray-200 p-3">
          <pre
            data-testid="code-block"
            className="overflow-x-auto rounded bg-gray-900 p-3 text-xs leading-relaxed text-gray-100"
          >
            <code>{code}</code>
          </pre>
          <div className="mt-3">
            <StubButton label="Edit & rerun" phase="Phase 2" onStub={onStub} />
          </div>
        </div>
      )}
    </div>
  )
}
