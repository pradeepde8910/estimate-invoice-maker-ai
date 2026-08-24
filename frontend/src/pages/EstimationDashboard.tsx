import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import StatCard from '../components/StatCard'
import HeroStat from '../components/HeroStat'
import { inr, compactInr } from '../components/EstimationResult'
import ConfirmModal from '../components/ConfirmModal'
import { getAnalytics, deleteEstimation } from '../api/client'
import type { Analytics, DocumentSummary } from '../api/types'
import { useJob } from '../JobContext'

export default function EstimationDashboard() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()
  const { job, setJobId } = useJob()
  const jobIsActive = job?.status === 'queued' || job?.status === 'running'

  function goToNewEstimation() {
    // Same fix as the sidebar link: only jump straight into the form if
    // there's no in-flight job to keep tracking, otherwise this would land
    // on the last completed job's results instead of a blank form.
    if (!jobIsActive) setJobId(null)
    navigate('/estimation/new')
  }

  function refresh() {
    getAnalytics()
      .then(setData)
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    setError(null)
    try {
      await deleteEstimation(deleteTarget.base_name)
      setDeleteTarget(null)
      refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  function downloadCsv() {
    if (!data) return
    const rows = [
      ['Client', 'Project', 'Grand Total', 'Timeline (weeks)', 'Modified'],
      ...data.recent.map((e) => [e.client_name, e.project_name, String(e.grand_total ?? ''), String(e.timeline_weeks ?? ''), e.modified]),
    ]
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `estimation-statement-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Topbar showBack title="Estimation Dashboard" subtitle="Overview of every estimation you've created." />
      <div className="p-8 space-y-6">
        <div className="flex justify-end">
          <button
            onClick={goToNewEstimation}
            className="text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white px-5 py-2.5 rounded-full"
          >
            + New Estimation
          </button>
        </div>

        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}
        {!data ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
              <HeroStat tone="coral" label="Total Project Value" value={compactInr(data.total_project_value)} sub="All estimations" />
              <HeroStat tone="mint" label="Average Estimation" value={compactInr(data.average_estimation_value)} sub="Per project" />
              <Card className="flex flex-col justify-center">
                <StatCard label="Today" value={data.today_count} sub="Estimations created" />
              </Card>
              <Card className="flex flex-col justify-center">
                <StatCard label="This Month" value={data.month_count} sub="Estimations created" />
              </Card>
            </div>

            <Card
              title="Recent Estimations"
              action={
                <div className="flex items-center gap-4">
                  <button onClick={downloadCsv} className="text-xs font-medium text-brand-600 hover:underline">
                    ⬇ Download statement (CSV)
                  </button>
                  <button onClick={() => navigate('/estimation/list')} className="text-xs font-medium text-brand-600 hover:underline">
                    View all →
                  </button>
                </div>
              }
            >
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-400 uppercase tracking-wide">
                      <th className="py-2 pr-4">Client</th>
                      <th className="py-2 pr-4">Project</th>
                      <th className="py-2 pr-4">Value</th>
                      <th className="py-2 pr-4">Modified</th>
                      <th className="py-2 pr-4 w-10"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.recent.map((e) => (
                      <tr key={e.base_name} className="hover:bg-slate-50">
                        <td className="py-2.5 pr-4 text-slate-700">{e.client_name}</td>
                        <td className="py-2.5 pr-4 text-slate-600 truncate max-w-[220px]">{e.project_name}</td>
                        <td className="py-2.5 pr-4 font-medium text-slate-800 tabular-nums">
                          {e.grand_total != null ? inr(e.grand_total) : '—'}
                        </td>
                        <td className="py-2.5 pr-4 text-slate-400 text-xs">{new Date(e.modified).toLocaleDateString()}</td>
                        <td className="py-2.5 pr-4 text-right flex items-center justify-end gap-1">
                          <button
                            onClick={() => navigate(`/estimation/${e.base_name}`)}
                            className="text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 hover:text-brand-700 px-3 py-1.5 rounded-full transition-colors mr-1"
                          >
                            View
                          </button>
                          <button
                            onClick={(ev) => {
                              ev.stopPropagation()
                              setDeleteTarget(e)
                            }}
                            title="Delete Estimation"
                            className="w-8 h-8 rounded-full text-slate-300 hover:text-coral-600 hover:bg-coral-50 inline-flex items-center justify-center transition-colors"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M3 6h18"></path>
                              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                            </svg>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>

      <ConfirmModal
        isOpen={deleteTarget !== null}
        title="Delete this estimation?"
        message={`This will permanently delete "${deleteTarget?.project_name ?? ''}" and any associated invoices. This cannot be undone.`}
        confirmText={deleting ? 'Deleting…' : 'Delete'}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
