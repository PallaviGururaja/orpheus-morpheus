'use client'

import { useCallback, useRef, useState } from 'react'
import AnswerBlock from './components/AnswerBlock'
import FileBrowser from './components/FileBrowser'
import HistoryPanel from './components/HistoryPanel'
import ProfileCard from './components/ProfileCard'
import QuestionBox from './components/QuestionBox'
import Sidebar from './components/Sidebar'
import { Toast } from './components/Stub'
import UploadPanel from './components/UploadPanel'
import { ApiError, ask, listQueries, loadLocalDataset, uploadDataset } from './lib/api'
import type { AskResponse, DatasetResponse, QuerySummary } from './lib/types'

// Local data-analysis workbench (Phase 1). One CSV → profile → one question →
// verified, audited answer with table + chart + generated code.
export default function Home() {
  const [dataset, setDataset] = useState<DatasetResponse | null>(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [lastQuestion, setLastQuestion] = useState('')
  const [askLoading, setAskLoading] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)

  const [queries, setQueries] = useState<QuerySummary[]>([])
  const [toast, setToast] = useState<string | null>(null)
  const [browserOpen, setBrowserOpen] = useState(false)

  // The UploadPanel registers its "open file dialog" here so the sidebar
  // "Add dataset" button can trigger the same picker.
  const openPickerRef = useRef<(() => void) | null>(null)

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(null), 3500)
  }, [])

  const refreshHistory = useCallback(async (sessionId: string) => {
    try {
      setQueries(await listQueries(sessionId))
    } catch {
      // History is a non-blocking side panel; ignore transient failures.
    }
  }, [])

  const handleUpload = useCallback(
    async (file: File) => {
      setUploadLoading(true)
      setUploadError(null)
      try {
        const result = await uploadDataset(file, dataset?.session_id ?? null)
        setDataset(result)
        setAnswer(null)
        setAskError(null)
        void refreshHistory(result.session_id)
      } catch (e) {
        setUploadError(
          e instanceof ApiError
            ? e.message
            : 'Could not reach the server — is it running on this machine?',
        )
      } finally {
        setUploadLoading(false)
      }
    },
    [dataset, refreshHistory],
  )

  const applyDataset = useCallback(
    (result: DatasetResponse) => {
      setDataset(result)
      setAnswer(null)
      setAskError(null)
      void refreshHistory(result.session_id)
    },
    [refreshHistory],
  )

  const handleLoadLocal = useCallback(
    async (path: string) => {
      setBrowserOpen(false)
      setUploadLoading(true)
      setUploadError(null)
      try {
        applyDataset(await loadLocalDataset(path, dataset?.session_id ?? null))
      } catch (e) {
        setUploadError(
          e instanceof ApiError ? e.message : 'Could not load that file.',
        )
      } finally {
        setUploadLoading(false)
      }
    },
    [dataset, applyDataset],
  )

  const handleAsk = useCallback(
    async (question: string) => {
      if (!dataset) return
      setAskLoading(true)
      setAskError(null)
      setLastQuestion(question)
      try {
        const result = await ask(dataset.session_id, [dataset.dataset_id], question)
        setAnswer(result)
        void refreshHistory(dataset.session_id)
      } catch (e) {
        setAnswer(null)
        if (e instanceof ApiError) {
          setAskError(
            e.status === 503
              ? 'Local model unavailable — is Ollama running?'
              : e.message,
          )
        } else {
          setAskError('Could not reach the server — is it running on this machine?')
        }
      } finally {
        setAskLoading(false)
      }
    },
    [dataset, refreshHistory],
  )

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <header className="flex items-center gap-3 border-b border-gray-200 bg-white px-5 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
          ◆
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-gray-900">
            Local Data Analyst
          </h1>
          <p className="text-xs text-gray-400">Fully local · nothing leaves this machine</p>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <Sidebar
          dataset={dataset}
          onStub={showToast}
          onAddDataset={() => setBrowserOpen(true)}
        />

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-6">
            <UploadPanel
              onFile={handleUpload}
              loading={uploadLoading}
              error={uploadError}
              hasDataset={!!dataset}
              registerOpen={open => {
                openPickerRef.current = open
              }}
              onBrowse={() => setBrowserOpen(true)}
            />

            {dataset && <ProfileCard dataset={dataset} />}

            {dataset && (
              <QuestionBox onAsk={handleAsk} loading={askLoading} disabled={!dataset} />
            )}

            {askError && (
              <div
                role="alert"
                data-testid="ask-error"
                className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
              >
                <p className="font-medium">{askError}</p>
                {lastQuestion && (
                  <p className="mt-1 text-xs text-red-500">
                    Your question was kept: &ldquo;{lastQuestion}&rdquo;
                  </p>
                )}
              </div>
            )}

            {askLoading && (
              <div
                data-testid="ask-loading"
                className="rounded-xl border border-gray-200 bg-white p-5 text-sm text-gray-500 shadow-sm"
              >
                Analyzing locally… writing Python, running it against your data, and verifying the
                result.
              </div>
            )}

            {answer && !askLoading && (
              <AnswerBlock answer={answer} question={lastQuestion} onStub={showToast} />
            )}

            {!dataset && !uploadLoading && (
              <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
                <p className="text-sm font-medium text-gray-700">Start by loading a dataset</p>
                <p className="mt-1 text-sm text-gray-400">
                  Upload a CSV to see its profile, then ask questions in plain English.
                </p>
              </div>
            )}
          </div>
        </main>

        <HistoryPanel queries={queries} onStub={showToast} />
      </div>

      {browserOpen && (
        <FileBrowser onPick={handleLoadLocal} onClose={() => setBrowserOpen(false)} />
      )}

      <Toast message={toast} onClose={() => setToast(null)} />
    </div>
  )
}
