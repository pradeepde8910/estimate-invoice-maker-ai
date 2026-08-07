import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import Stepper from '../components/Stepper'
import CircularGauge from '../components/CircularGauge'
import EstimationResult from '../components/EstimationResult'
import { useJob } from '../JobContext'
import { createJob, cancelJob } from '../api/client'
import type { Job } from '../api/types'

type Mode = 'file' | 'url' | 'text'

function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes === 0) return `${seconds}s`
  return `${minutes}m ${seconds}s`
}

/** Rough ETA: extrapolates from how long the completed steps took so far.
 * Only meaningful once at least one step has finished — before that there's
 * no data to extrapolate from. */
function estimateRemaining(job: Job): string | null {
  if (!job.created_at) return null
  const completedSteps = job.status === 'queued' ? 0 : job.step_index + 1
  if (completedSteps <= 0 || completedSteps >= job.steps.length) return null

  const elapsedMs = Date.now() - new Date(job.created_at).getTime()
  if (elapsedMs <= 0) return null

  const avgPerStepMs = elapsedMs / completedSteps
  const remainingSteps = job.steps.length - completedSteps
  return formatDuration(avgPerStepMs * remainingSteps)
}

export default function NewEstimation() {
  const { job, jobId, setJobId } = useJob()
  const [showForm, setShowForm] = useState(!jobId)
  const [cancelling, setCancelling] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    setShowForm(!jobId)
  }, [jobId])

  const isActive = job?.status === 'queued' || job?.status === 'running'

  const progressPct =
    !job || job.status === 'queued'
      ? 4
      : job.status === 'complete'
      ? 100
      : Math.round(((job.step_index + 1) / job.steps.length) * 100)

  async function handleCancel() {
    if (!jobId) return
    setCancelling(true)
    try {
      await cancelJob(jobId)
    } catch {
      // Job may have already finished/failed on its own — the next poll
      // will reflect whatever its real status is.
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="flex-1">
      <Topbar title="New Estimation" subtitle="Upload a requirement document to get an AI-generated cost & timeline estimate." />
      <div className="p-8 space-y-6">
        {!showForm && (
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-500">
              {job ? (
                <>
                  Estimating for <span className="font-semibold text-slate-800">{job.result?.client_name || job.source_name}</span>
                </>
              ) : (
                'Loading…'
              )}
            </div>
            <div className="flex items-center gap-3">
              {isActive ? (
                <button
                  onClick={handleCancel}
                  disabled={cancelling}
                  className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-coral-600 hover:bg-coral-50 disabled:opacity-50"
                >
                  {cancelling ? 'Cancelling…' : 'Cancel Estimation'}
                </button>
              ) : (
                <>
                  <button
                    onClick={() => navigate('/estimation/list')}
                    className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50"
                  >
                    View all estimations
                  </button>
                  <button
                    onClick={() => {
                      setJobId(null)
                      setShowForm(true)
                    }}
                    className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-brand-700 hover:bg-brand-50"
                  >
                    + New Estimation
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {showForm && (
          <NewEstimationForm
            onCreated={(id) => {
              setJobId(id)
              setShowForm(false)
            }}
            onCancel={job ? () => setShowForm(false) : undefined}
          />
        )}

        {!showForm && job && job.status !== 'complete' && (
          <Card>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
              <div className="lg:col-span-2">
                <Stepper steps={job.steps} stepIndex={job.status === 'queued' ? -1 : job.step_index} failed={job.status === 'failed'} />
                <div
                  className={`mt-4 rounded-2xl px-4 py-3 text-sm ${
                    job.status === 'failed'
                      ? 'bg-coral-50 text-coral-700'
                      : job.status === 'cancelled'
                      ? 'bg-slate-100 text-slate-600'
                      : 'bg-brand-50 text-brand-700'
                  }`}
                >
                  {job.status === 'failed'
                    ? `Error: ${job.error}`
                    : job.status === 'cancelled'
                    ? 'Estimation cancelled.'
                    : (() => {
                        const eta = estimateRemaining(job)
                        return `Working through "${job.steps[job.step_index] ?? job.steps[0]}"...${eta ? ` (~${eta} remaining)` : ''}`
                      })()}
                </div>
              </div>
              <div className="flex flex-col items-center">
                <CircularGauge
                  value={progressPct}
                  label={job.status === 'failed' ? 'Failed' : job.status === 'cancelled' ? 'Cancelled' : 'In progress'}
                />
              </div>
            </div>
          </Card>
        )}

        {!showForm && job?.status === 'complete' && job.result && (
          <EstimationResult result={job.result} docSource="job" docId={job.id} baseName={job.base_name} />
        )}
      </div>
    </div>
  )
}

function NewEstimationForm({ onCreated, onCancel }: { onCreated: (jobId: string) => void; onCancel?: () => void }) {
  const [mode, setMode] = useState<Mode>('file')
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const canSubmit =
    !submitting && ((mode === 'file' && file) || (mode === 'url' && url.trim()) || (mode === 'text' && text.trim().length > 20))

  async function handleSubmit() {
    setSubmitting(true)
    setError(null)
    try {
      const { job_id } = await createJob({
        file: mode === 'file' && file ? file : undefined,
        url: mode === 'url' ? url.trim() : undefined,
        text: mode === 'text' ? text.trim() : undefined,
        generate_brd: true,
        generate_srs: true,
      })
      onCreated(job_id)
    } catch (e: any) {
      setError(e.message || 'Failed to start estimation')
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-6">
        <div className="flex gap-2 bg-slate-50 rounded-full p-1 w-fit">
          {(['file', 'url', 'text'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-full text-sm font-medium capitalize transition-colors ${
                mode === m ? 'bg-white shadow-card text-brand-700' : 'text-slate-500'
              }`}
            >
              {m === 'file' ? 'Upload File' : m === 'url' ? 'From URL' : 'Paste Text'}
            </button>
          ))}
        </div>
        {onCancel && (
          <button onClick={onCancel} className="text-sm text-slate-400 hover:text-slate-600">
            Cancel
          </button>
        )}
      </div>

      {mode === 'file' && (
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const f = e.dataTransfer.files?.[0]
            if (f) setFile(f)
          }}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-3xl py-12 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-brand-400 bg-brand-50' : 'border-slate-200 hover:border-brand-300'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md,.csv"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <div className="text-4xl mb-3">📄</div>
          {file ? (
            <div>
              <div className="font-medium text-slate-800">{file.name}</div>
              <div className="text-xs text-slate-400 mt-1">{(file.size / 1024).toFixed(0)} KB · Click to change</div>
            </div>
          ) : (
            <div>
              <div className="font-medium text-slate-700">Drag & drop a PDF, DOCX or text file</div>
              <div className="text-xs text-slate-400 mt-1">or click to browse</div>
            </div>
          )}
        </div>
      )}

      {mode === 'url' && (
        <div>
          <label className="text-sm font-medium text-slate-600">Document URL</label>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/requirements.pdf"
            className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
          />
        </div>
      )}

      {mode === 'text' && (
        <div>
          <label className="text-sm font-medium text-slate-600">Requirement Description</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            placeholder="Prepared for Acme Corp. Build an e-commerce platform with user authentication, product catalog, cart, and payments..."
            className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300 resize-none"
          />
          <p className="text-xs text-slate-400 mt-2">Tip: mention the client/company name so it's captured correctly.</p>
        </div>
      )}

      {error && <div className="mt-4 text-sm text-coral-600 bg-coral-50 rounded-2xl px-3 py-2">{error}</div>}

      <button
        disabled={!canSubmit}
        onClick={handleSubmit}
        className="mt-6 w-full bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-medium py-3 rounded-full transition-colors"
      >
        {submitting ? 'Starting estimation…' : 'Start Estimation'}
      </button>
    </Card>
  )
}
