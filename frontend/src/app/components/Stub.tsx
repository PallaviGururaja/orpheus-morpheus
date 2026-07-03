'use client'

// Clearly-labelled, non-functional previews of later-phase features.
// They must read as roadmap, never as bugs: greyed, cursor-not-allowed, a
// "Coming soon" badge, and a toast on click that names the phase.

export function ComingSoonBadge({ phase }: { phase: string }) {
  return (
    <span className="ml-2 shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
      {phase}
    </span>
  )
}

interface StubButtonProps {
  label: string
  phase: string
  onStub: (message: string) => void
  className?: string
  icon?: React.ReactNode
}

export function StubButton({ label, phase, onStub, className, icon }: StubButtonProps) {
  return (
    <button
      type="button"
      aria-disabled="true"
      title={`${label} — coming in ${phase}`}
      onClick={() => onStub(`${label} is coming in ${phase}.`)}
      className={
        'flex w-full items-center justify-between gap-2 rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-2 text-left text-sm text-gray-400 transition hover:bg-gray-100 ' +
        (className ?? '')
      }
    >
      <span className="flex items-center gap-2">
        {icon}
        {label}
      </span>
      <ComingSoonBadge phase={phase} />
    </button>
  )
}

export function Toast({ message, onClose }: { message: string | null; onClose: () => void }) {
  if (!message) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-gray-900 px-4 py-2.5 text-sm text-white shadow-lg"
    >
      <span>{message}</span>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss"
        className="ml-3 text-gray-400 hover:text-white"
      >
        ×
      </button>
    </div>
  )
}
