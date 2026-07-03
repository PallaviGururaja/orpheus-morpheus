'use client'

import { useState } from 'react'

// Plain-English question input → GET /ask/stream (parent owns the call). Disabled
// until a dataset is loaded. Live progress (step counter + timer) renders in the
// parent's StepTrace while the agent streams.
export default function QuestionBox({
  onAsk,
  loading,
  disabled,
}: {
  onAsk: (question: string) => void
  loading: boolean
  disabled: boolean
}) {
  const [question, setQuestion] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || loading || disabled) return
    onAsk(q)
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <label htmlFor="question" className="mb-1.5 block text-sm font-medium text-gray-700">
        Ask a question about your data
      </label>
      <textarea
        id="question"
        data-testid="question-input"
        rows={2}
        value={question}
        onChange={e => setQuestion(e.target.value)}
        disabled={disabled || loading}
        placeholder={
          disabled ? 'Upload a CSV first…' : 'e.g. What is the total revenue by region?'
        }
        className="w-full resize-none rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        onKeyDown={e => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(e)
        }}
      />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          Runs locally · live step trace &amp; timer
        </span>
        <button
          type="submit"
          data-testid="ask-button"
          disabled={disabled || loading || !question.trim()}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading && (
            <svg
              className="h-4 w-4 animate-spin motion-reduce:animate-none"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          )}
          {loading ? 'Analyzing locally…' : 'Ask'}
        </button>
      </div>
    </form>
  )
}
