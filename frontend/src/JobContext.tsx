import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { getJob, ApiError } from './api/client'
import type { Job } from './api/types'

/** Percentage through the estimation pipeline, derived client-side since the
 * backend doesn't return one — kept here so the sidebar badge and the
 * NewEstimation gauge never drift apart. */
export function getJobProgressPct(job: Job | null): number {
  if (!job || job.status === 'queued') return 4
  if (job.status === 'complete') return 100
  return Math.round(((job.step_index + 1) / job.steps.length) * 100)
}

interface JobContextValue {
  jobId: string | null
  job: Job | null
  setJobId: (id: string | null) => void
  notifications: string[]
  clearNotifications: () => void
  /** Re-fetches the current job once and updates `job` with the result.
   * Needed because polling stops once a job reaches 'complete' (see the
   * effect below) — so any change made after that point (e.g. confirming
   * client identity from the estimation-result screen) has no other way
   * to reach the `job` object callers are still reading from. */
  refreshJob: () => Promise<void>
}

const JobContext = createContext<JobContextValue | null>(null)

const STORAGE_KEY = 'docparser.jobId'

export function JobProvider({ children }: { children: React.ReactNode }) {
  const [jobId, setJobIdState] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY))
  const [job, setJob] = useState<Job | null>(null)
  const [notifications, setNotifications] = useState<string[]>([])
  const lastStatus = useRef<string | null>(null)

  const setJobId = useCallback((id: string | null) => {
    setJobIdState(id)
    lastStatus.current = null
    setJob(null)
    if (id) localStorage.setItem(STORAGE_KEY, id)
    else localStorage.removeItem(STORAGE_KEY)
  }, [])

  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const j = await getJob(jobId)
        if (cancelled) return
        setJob(j)
        if (lastStatus.current !== j.status) {
          if (j.status === 'complete') {
            setNotifications((n) => [
              ...n,
              `Estimation ready for ${j.result?.client_name || j.result?.project_name || j.source_name}`,
            ])
          } else if (j.status === 'failed') {
            setNotifications((n) => [...n, `Estimation failed: ${j.error ?? 'unknown error'}`])
          } else if (j.status === 'cancelled') {
            setNotifications((n) => [...n, `Estimation cancelled for ${j.source_name}`])
          }
          lastStatus.current = j.status
        }
        if (j.status === 'queued' || j.status === 'running') {
          timer = window.setTimeout(poll, 1800)
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          // Job no longer exists (e.g. backend restarted) — stop polling and
          // clear it so the UI falls back to the "start a new one" state
          // instead of silently hanging with nothing rendered.
          setJobIdState(null)
          localStorage.removeItem(STORAGE_KEY)
          setJob(null)
          return
        }
        timer = window.setTimeout(poll, 3000)
      }
    }
    poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [jobId])

  const clearNotifications = useCallback(() => setNotifications([]), [])

  const refreshJob = useCallback(async () => {
    if (!jobId) return
    try {
      const j = await getJob(jobId)
      setJob(j)
    } catch {
      // Best-effort — if this fails the caller's own UI already reflects
      // what it just saved locally; a stale `job` object here just means
      // the next unrelated re-render shows old data, not a broken save.
    }
  }, [jobId])

  return (
    <JobContext.Provider value={{ jobId, job, setJobId, notifications, clearNotifications, refreshJob }}>
      {children}
    </JobContext.Provider>
  )
}

export function useJob() {
  const ctx = useContext(JobContext)
  if (!ctx) throw new Error('useJob must be used within JobProvider')
  return ctx
}
