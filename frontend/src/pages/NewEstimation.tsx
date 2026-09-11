import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import Stepper from '../components/Stepper'
import CircularGauge from '../components/CircularGauge'
import EstimationResult from '../components/EstimationResult'
import ClientDetailsEditor from '../components/ClientDetailsEditor'
import { useJob, getJobProgressPct } from '../JobContext'
import { createJob, cancelJob } from '../api/client'
import type { Job } from '../api/types'

type Mode = 'file' | 'url' | 'text'

function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000))
  if (totalSeconds < 30) return 'less than a minute'
  
  const minutes = Math.round(totalSeconds / 60)
  if (minutes <= 1) return 'about a minute'
  
  return `around ${minutes} mins`
}

/** Rough ETA: Uses a blended average of actual time and a 20s baseline to ensure smooth, robust UX. */
function estimateRemaining(job: Job): string | null {
  if (!job.created_at) return null
  
  const completedSteps = job.status === 'queued' ? 0 : job.step_index
  if (completedSteps >= job.steps.length) return null

  const createdTime = new Date(job.created_at).getTime()
  if (isNaN(createdTime)) return null
  const elapsedMs = Date.now() - createdTime
  if (isNaN(elapsedMs) || elapsedMs <= 0) return null

  const DEFAULT_STEP_MS = 20000 // 20s baseline per step
  const remainingSteps = job.steps.length - completedSteps

  if (completedSteps <= 0) {
    return formatDuration(remainingSteps * DEFAULT_STEP_MS)
  }

  // Cap actual avg at 40s to prevent wild spikes if one step stalls
  const actualAvg = Math.min(elapsedMs / completedSteps, 40000)
  
  // Blend actual average and default to smooth out the ETA and prevent jumping
  const blendedAvg = (actualAvg * completedSteps + DEFAULT_STEP_MS * remainingSteps) / job.steps.length
  
  return formatDuration(blendedAvg * remainingSteps)
}

export default function NewEstimation() {
  const { job, jobId, setJobId, refreshJob } = useJob()
  const [showForm, setShowForm] = useState(!jobId)
  const [cancelling, setCancelling] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    setShowForm(!jobId)
  }, [jobId])

  const isActive = job?.status === 'queued' || job?.status === 'running'

  const progressPct = getJobProgressPct(job)

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
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar title="New Estimation" subtitle="Upload a requirement document to get an AI-generated cost & timeline estimate." />
      <div className="p-8 space-y-6">
        {!showForm && (
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
            <div className="text-sm text-slate-500 min-w-0 flex items-baseline gap-1">
              {job ? (
                <>
                  <span className="shrink-0">Estimating for</span>
                  <span
                    className="font-semibold text-slate-800 truncate"
                    title={job.result?.client_name || job.source_name}
                  >
                    {job.result?.client_name || job.source_name}
                  </span>
                </>
              ) : (
                'Loading…'
              )}
            </div>
            <div className="flex flex-wrap items-center gap-3">
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
          <>
            {!job.result.converted_project_id && (
              <ClientDetailsEditor
                baseName={job.base_name || ''}
                clientInfo={job.result.client_info}
                onSaved={() => {
                  // `job` comes from JobContext and stops polling once the
                  // job reaches 'complete' — without this, the just-saved
                  // client identity would never reach this screen, and
                  // ClientDetailsEditor's read-only view would flip back to
                  // showing the pre-save (empty) data right after a
                  // successful save, looking like the save silently failed.
                  refreshJob()
                }}
              />
            )}
            <EstimationResult result={job.result} docSource="job" docId={job.id} baseName={job.base_name} />
          </>
        )}
      </div>
    </div>
  )
}

const isValidUrl = (urlString: string) => {
  try {
    const parsed = new URL(urlString)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch (e) {
    return false
  }
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

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB

  const handleFileSelect = (f: File | undefined | null) => {
    if (!f) {
      setFile(null)
      return
    }
    if (f.size > MAX_FILE_SIZE) {
      setError('File size must be less than 5MB')
      setFile(null)
      return
    }
    setError(null)
    setFile(f)
  }

  const canSubmit = !submitting

  async function handleSubmit() {
    setSubmitting(true)
    setError(null)

    if (mode === 'file' && !file) {
      setError('File is required')
      setSubmitting(false)
      return
    }
    if (mode === 'url' && (!url.trim() || !isValidUrl(url.trim()))) {
      setError('Please enter a valid HTTP/HTTPS URL.')
      setSubmitting(false)
      return
    }
    if (mode === 'text' && text.trim().length === 0) {
      setError('Text is required')
      setSubmitting(false)
      return
    }
    if (mode === 'text' && text.trim().length <= 20) {
      setError('Please provide a more detailed requirement description (at least 20 characters).')
      setSubmitting(false)
      return
    }
    if (mode === 'text' && text.length > 20000) {
      setError('Text is too long (maximum 20,000 characters). Please provide a more concise description or use a document upload.')
      setSubmitting(false)
      return
    }
    if (mode === 'text' && /[\uFFFD\x00-\x08\x0B\x0C\x0E-\x1F]/.test(text)) {
      setError('Text contains unsupported or invalid characters. Please remove any special symbols or formatting.')
      setSubmitting(false)
      return
    }

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
      <div className="flex flex-wrap items-center justify-between gap-y-2 mb-6">
        <div className="flex flex-wrap gap-2 bg-slate-50 rounded-full p-1 w-fit">
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
            handleFileSelect(e.dataTransfer.files?.[0])
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
            onChange={(e) => handleFileSelect(e.target.files?.[0])}
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
              <div className="text-xs text-slate-400 mt-1">or click to browse (Max size: 5MB)</div>
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
            className={`mt-2 w-full border ${
              url.trim() && !isValidUrl(url.trim()) ? 'border-coral-500 focus:ring-coral-300' : 'border-slate-200 focus:ring-brand-300'
            } rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2`}
          />
          {url.trim() && !isValidUrl(url.trim()) && (
            <p className="text-xs text-coral-500 mt-2">Please enter a valid HTTP/HTTPS URL.</p>
          )}
        </div>
      )}

      {mode === 'text' && (
        <div>
          <label className="text-sm font-medium text-slate-600">Requirement Description</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            maxLength={20000}
            placeholder="Prepared for Acme Corp. Build an e-commerce platform with user authentication, product catalog, cart, and payments..."
            className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300 resize-none"
          />
          <div className="flex justify-between items-center mt-2">
            <p className="text-xs text-slate-400">Tip: mention the client/company name so it's captured correctly.</p>
            <p className={`text-xs ${text.length > 19000 ? 'text-coral-500 font-medium' : 'text-slate-400'}`}>
              {text.length.toLocaleString()} / 20,000
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="fixed top-4 left-4 right-4 sm:left-auto sm:right-6 sm:top-6 z-50 flex items-start gap-3 bg-white shadow-2xl rounded-2xl p-4 border-l-4 border-coral-500 animate-in fade-in slide-in-from-top-4 duration-300 sm:max-w-sm">
          <div className="bg-coral-50 text-coral-600 rounded-full p-1 mt-0.5">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-slate-800">Validation Error</h3>
            <p className="text-sm text-slate-600 mt-1">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-slate-600 transition-colors p-1">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

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
