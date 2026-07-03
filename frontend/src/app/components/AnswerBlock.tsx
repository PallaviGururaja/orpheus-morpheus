'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { AskResponse } from '../lib/types'
import ChartView from './ChartView'
import CodePanel from './CodePanel'

// Renders a completed answer: written text (markdown), summary table, optional
// chart, editable code panel (with rerun), and real Phase-2 follow-up chips.
export default function AnswerBlock({
  answer,
  question,
  followups,
  onFollowup,
  onRerun,
}: {
  answer: AskResponse
  question: string
  followups: string[]
  onFollowup: (question: string) => void
  onRerun: (code: string) => Promise<void>
}) {
  const columns = answer.result_table.length > 0 ? Object.keys(answer.result_table[0]) : []

  return (
    <section
      data-testid="answer-block"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <p className="mb-2 text-xs font-medium text-gray-400">You asked: {question}</p>

      <div className="mb-1 flex items-center gap-2">
        <span
          className={
            'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ' +
            (answer.verified ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500')
          }
        >
          {answer.verified ? '✓ Verified' : 'Unverified'}
        </span>
        <span className="text-xs text-gray-400">
          {answer.steps_used} steps · {(answer.elapsed_ms / 1000).toFixed(1)}s ·{' '}
          {answer.prompt_tokens + answer.completion_tokens} tokens
        </span>
      </div>

      <div
        data-testid="answer-text"
        className="prose prose-sm mt-2 max-w-none text-[15px] leading-relaxed text-gray-800 [&_code]:rounded [&_code]:bg-gray-100 [&_code]:px-1 [&_table]:text-sm"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.answer_text}</ReactMarkdown>
      </div>

      {answer.result_table.length > 0 && (
        <div className="mt-4 overflow-x-auto" data-testid="result-table">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-gray-500">
                {columns.map(c => (
                  <th key={c} className="py-1.5 pr-4 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {answer.result_table.map((row, i) => (
                <tr key={i} className="border-b border-gray-100 last:border-0">
                  {columns.map(c => (
                    <td key={c} className="py-1.5 pr-4 text-gray-800">
                      {formatCell(row[c])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ChartView spec={answer.chart_spec} rows={answer.result_table} />

      <CodePanel code={answer.code} onRerun={onRerun} />

      {/* Follow-up chips (real, Phase 2) */}
      {followups.length > 0 && (
        <div className="mt-5 border-t border-gray-100 pt-4">
          <div className="mb-2 text-xs font-medium text-gray-400">Suggested follow-ups</div>
          <div className="flex flex-wrap gap-2" data-testid="followups">
            {followups.map(s => (
              <button
                key={s}
                type="button"
                data-testid="followup-chip"
                onClick={() => onFollowup(s)}
                className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 transition hover:bg-blue-100"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function formatCell(value: string | number | boolean | null): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}
