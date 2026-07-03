'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import AnswerBlock from './components/AnswerBlock'
import FileBrowser from './components/FileBrowser'
import HistoryPanel from './components/HistoryPanel'
import ProfileCard from './components/ProfileCard'
import QuestionBox from './components/QuestionBox'
import Sidebar from './components/Sidebar'
import StepTrace from './components/StepTrace'
import { Toast } from './components/Stub'
import UploadPanel from './components/UploadPanel'
import {
  ApiError,
  getFollowups,
  listQueries,
  loadLocalDataset,
  rerunQuery,
  streamAsk,
  uploadDataset,
} from './lib/api'
import type { AskResponse, DatasetResponse, QuerySummary } from './lib/types'

// Local data-analysis workbench (Phase 2). Multiple CSVs per session → profiles →
// a question streamed via GET /ask/stream (live step counter + timer + streaming
// answer) → verified, audited answer with table + chart + editable/rerunnable code
// + real follow-up chips.
export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [datasets, setDatasets] = useState<DatasetResponse[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [followups, setFollowups] = useState<string[]>([])
  const [lastQuestion, setLastQuestion] = useState('')
  const [askError, setAskError] = useState<string | null>(null)

  // Streaming (Phase 2) state.
  const [streaming, setStreaming] = useState(false)
  const [step, setStep] = useState(0)
  const [totalSteps, setTotalSteps] = useState(6)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [streamedText, setStreamedText] = useState('')

  const [queries, setQueries] = useState<QuerySummary[]>([])
  const [toast, setToast] = useState<string | null>(null)
  const [browserOpen, setBrowserOpen] = useState(false)

  const openPickerRef = useRef<(() => void) | null>(null)
  const timerRef = useRef<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
      abortRef.current?.abort()
    }
  }, [])

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(null), 3500)
  }, [])

  const refreshHistory = useCallback(async (sid: string) => {
    try {
      setQueries(await listQueries(sid))
    } catch {
      // History is a non-blocking side panel; ignore transient failures.
    }
  }, [])

  const loadFollowups = useCallback(async (queryId: string) => {
    try {
      setFollowups(await getFollowups(queryId))
    } catch {
      setFollowups([])
    }
  }, [])

  // Append (or replace-by-id) a freshly loaded dataset and keep the session.
  const applyDataset = useCallback(
    (result: DatasetResponse) => {
      setSessionId(result.session_id)
      setDatasets(prev => {
        const rest = prev.filter(d => d.dataset_id !== result.dataset_id)
        return [...rest, result]
      })
      setSelectedIds(prev =>
        prev.includes(result.dataset_id) ? prev : [...prev, result.dataset_id],
      )
      void refreshHistory(result.session_id)
    },
    [refreshHistory],
  )

  const handleUpload = useCallback(
    async (file: File) => {
      setUploadLoading(true)
      setUploadError(null)
      try {
        applyDataset(await uploadDataset(file, sessionId))
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
    [sessionId, applyDataset],
  )

  const handleLoadLocal = useCallback(
    async (path: string) => {
      setBrowserOpen(false)
      setUploadLoading(true)
      setUploadError(null)
      try {
        applyDataset(await loadLocalDataset(path, sessionId))
      } catch (e) {
        setUploadError(e instanceof ApiError ? e.message : 'Could not load that file.')
      } finally {
        setUploadLoading(false)
      }
    },
    [sessionId, applyDataset],
  )

  const toggleDataset = useCallback((datasetId: string) => {
    setSelectedIds(prev =>
      prev.includes(datasetId)
        ? prev.filter(id => id !== datasetId)
        : [...prev, datasetId],
    )
  }, [])

  // No server-side delete route (see spec/api.md) — removal drops the dataset from
  // the session's working set so it no longer flows into /ask.
  const removeDataset = useCallback((datasetId: string) => {
    setDatasets(prev => prev.filter(d => d.dataset_id !== datasetId))
    setSelectedIds(prev => prev.filter(id => id !== datasetId))
  }, [])

  const runQuestion = useCallback(
    async (question: string) => {
      if (!sessionId || datasets.length === 0 || streaming) return
      const ids =
        selectedIds.length > 0 ? selectedIds : datasets.map(d => d.dataset_id)

      setAskError(null)
      setAnswer(null)
      setFollowups([])
      setLastQuestion(question)
      setStreamedText('')
      setStep(0)
      setTotalSteps(6)
      setElapsedMs(0)
      setStreaming(true)

      const startedAt = Date.now()
      timerRef.current = window.setInterval(
        () => setElapsedMs(Date.now() - startedAt),
        200,
      )
      const controller = new AbortController()
      abortRef.current = controller

      let sawError = false
      try {
        await streamAsk(
          sessionId,
          ids,
          question,
          {
            onStep: e => {
              setStep(e.step)
              setTotalSteps(e.total_estimate)
            },
            onToken: t => setStreamedText(prev => prev + t),
            onDone: data => {
              setAnswer(data)
              void refreshHistory(sessionId)
              void loadFollowups(data.query_id)
            },
            onError: err => {
              sawError = true
              setAskError(
                err.status === 503 || err.code === 'MODEL_UNAVAILABLE'
                  ? 'Local model unavailable — is Ollama running?'
                  : err.message,
              )
            },
          },
          controller.signal,
        )
      } catch (e) {
        if (!(e instanceof DOMException && e.name === 'AbortError') && !sawError) {
          setAskError('Could not reach the server — is it running on this machine?')
        }
      } finally {
        if (timerRef.current) window.clearInterval(timerRef.current)
        timerRef.current = null
        abortRef.current = null
        setStreaming(false)
      }
    },
    [sessionId, datasets, selectedIds, streaming, refreshHistory, loadFollowups],
  )

  const handleRerun = useCallback(
    async (code: string) => {
      if (!answer || !sessionId) return
      const result = await rerunQuery(answer.query_id, code)
      setAnswer(result)
      void refreshHistory(sessionId)
      void loadFollowups(result.query_id)
    },
    [answer, sessionId, refreshHistory, loadFollowups],
  )

  const activeDataset = datasets[datasets.length - 1] ?? null

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <header className="flex items-center justify-between border-b border-slate-800 bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-3 text-white shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-base font-extrabold tracking-tight text-slate-900 shadow">
            EB
          </div>
          <div>
            <h1 className="text-base font-bold uppercase leading-tight tracking-[0.18em]">
              EBCO Private Limited
            </h1>
            <p className="text-xs font-medium tracking-wide text-slate-300">
              Data Analyst · fully local, nothing leaves this machine
            </p>
          </div>
        </div>
        <span className="hidden items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-300 sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          On-device AI
        </span>
      </header>

      <div className="flex min-h-0 flex-1">
        <Sidebar
          datasets={datasets}
          selectedIds={selectedIds}
          onToggle={toggleDataset}
          onRemove={removeDataset}
          onAddDataset={() => setBrowserOpen(true)}
          onStub={showToast}
        />

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-3xl flex-col gap-5 px-6 py-6">
            <UploadPanel
              onFile={handleUpload}
              loading={uploadLoading}
              error={uploadError}
              hasDataset={datasets.length > 0}
              registerOpen={open => {
                openPickerRef.current = open
              }}
              onBrowse={() => setBrowserOpen(true)}
            />

            {activeDataset && <ProfileCard dataset={activeDataset} />}

            {datasets.length > 0 && (
              <QuestionBox
                onAsk={runQuestion}
                loading={streaming}
                disabled={datasets.length === 0}
              />
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

            {streaming && (
              <StepTrace
                step={step}
                totalSteps={totalSteps}
                elapsedMs={elapsedMs}
                text={streamedText}
              />
            )}

            {answer && !streaming && (
              <AnswerBlock
                answer={answer}
                question={lastQuestion}
                followups={followups}
                onFollowup={runQuestion}
                onRerun={handleRerun}
              />
            )}

            {datasets.length === 0 && !uploadLoading && (
              <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
                <p className="text-sm font-medium text-gray-700">
                  Start by loading a dataset
                </p>
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
