'use client'

// Live progress for a streaming run (Phase 2): a real "Step 3 of 6" counter fed
// by `step` SSE events, an elapsed timer, and the answer text streamed in as
// `token` events arrive. Replaces the old static "Analyzing locally…" spinner.
export default function StepTrace({
  step,
  totalSteps,
  elapsedMs,
  text,
}: {
  step: number
  totalSteps: number
  elapsedMs: number
  text: string
}) {
  const shownStep = Math.max(step, 1)
  const shownTotal = Math.max(totalSteps, shownStep)
  return (
    <div
      data-testid="step-trace"
      className="rounded-xl border border-blue-200 bg-blue-50/60 p-5 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg
            className="h-4 w-4 animate-spin text-blue-600 motion-reduce:animate-none"
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
          <span data-testid="step-counter" className="text-sm font-medium text-blue-800">
            Step {shownStep} of {shownTotal}
          </span>
        </div>
        <span
          data-testid="step-timer"
          className="font-mono text-xs tabular-nums text-blue-600"
        >
          {(elapsedMs / 1000).toFixed(1)}s
        </span>
      </div>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
        <div
          className="h-full rounded-full bg-blue-500 transition-all"
          style={{ width: `${Math.min(100, (shownStep / shownTotal) * 100)}%` }}
        />
      </div>

      {text ? (
        <p
          data-testid="stream-text"
          className="mt-4 whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800"
        >
          {text}
          <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-blue-400 align-middle" />
        </p>
      ) : (
        <p className="mt-4 text-sm text-blue-700/70">
          Writing Python locally, running it against your data, and verifying the result…
        </p>
      )}
    </div>
  )
}
