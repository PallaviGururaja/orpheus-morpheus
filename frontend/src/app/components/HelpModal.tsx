'use client'

import { useState } from 'react'

interface Faq {
  q: string
  a: string
}

const FAQS: Faq[] = [
  {
    q: 'How do I load my data?',
    a: 'Click "Browse my computer" and pick a CSV or Excel (.xlsx) file from your Downloads, Documents, or Desktop. The in-app browser is the most reliable way; "Use system dialog" is a fallback. You can also drag a file onto the upload box.',
  },
  {
    q: "I can't see my files in the system dialog — what do I do?",
    a: 'Some Windows setups open the file dialog to the wrong folder. Use the "Browse my computer" button instead — it lists your files directly. If you must use the system dialog, paste the full file path (e.g. C:\\Users\\you\\Downloads\\data.csv) into the "File name" box and click Open.',
  },
  {
    q: 'How do I ask a question?',
    a: 'On the Ask tab, type a question in plain English in the box at the bottom (e.g. "What is the average revenue by region?") and press Ask. When you load a dataset, suggested starter questions appear above the box — click one to run it.',
  },
  {
    q: 'How long does an answer take?',
    a: 'Usually about 5–10 seconds. The agent plans, writes Python, runs it on your data, verifies the numbers, and writes the answer — you can watch each step live.',
  },
  {
    q: 'Is my data private?',
    a: 'Your raw data rows never leave this machine. Analysis runs locally. Only the column schema, the generated code, and aggregated results are sent to the cloud model to reason about — never the underlying rows.',
  },
  {
    q: 'Can I see and change the code it ran?',
    a: 'Yes. Every answer has a collapsible "Generated code" panel showing the exact Python. You can edit that code and click Rerun to get an updated result.',
  },
  {
    q: 'Can I use more than one dataset at once?',
    a: 'Yes. Load several files — they all appear in the left sidebar with checkboxes. Tick the ones you want and ask a question that spans them (e.g. a join or comparison across two files).',
  },
  {
    q: 'How do I build a dashboard?',
    a: 'Switch to the Dashboard tab. For a quick start, click one of the Predefined dashboards (Overview, Trends, Category breakdown) to auto-build charts from your columns. To build your own, click "+ Add widget" and drag a dimension and a measure from the palette onto the widget, then pick an aggregation and chart type.',
  },
  {
    q: 'Can I export results?',
    a: 'Yes. Use "Export CSV" under any answer to download its result table, and the Export CSV control on any dashboard widget to download that widget’s data.',
  },
  {
    q: 'How do I get back to a previous session?',
    a: 'Click "Switch session" in the left sidebar to see your earlier sessions and reopen one with its datasets and question history.',
  },
  {
    q: 'Where is my history kept?',
    a: 'Every question, the code that ran, and the result are recorded to a local audit trail (the History & Audit panel on the right of the Ask tab), so you can review what was asked and how each answer was produced.',
  },
  {
    q: 'What file types are supported?',
    a: 'CSV and Excel (.xlsx / .xls). Live database connections are coming in a later update.',
  },
]

export default function HelpModal({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Help &amp; FAQs</h2>
            <p className="text-xs text-gray-500">EBCO Private Limited · Data Analyst</p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close help"
          >
            ✕
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <ul className="flex flex-col gap-2">
            {FAQS.map((f, i) => {
              const isOpen = open === i
              return (
                <li key={i} className="rounded-lg border border-gray-200">
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                  >
                    <span className="text-sm font-medium text-gray-900">{f.q}</span>
                    <span className="shrink-0 text-gray-400">{isOpen ? '–' : '+'}</span>
                  </button>
                  {isOpen && (
                    <p className="whitespace-pre-line border-t border-gray-100 px-4 py-3 text-sm leading-relaxed text-gray-600">
                      {f.a}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        </div>

        <div className="border-t border-gray-200 px-5 py-3 text-xs text-gray-400">
          Still stuck? Reach out to your EBCO administrator.
        </div>
      </div>
    </div>
  )
}
