import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import StatCard from '../components/StatCard'
import HeroStat from '../components/HeroStat'
import { inr } from '../components/EstimationResult'
import { getAnalytics } from '../api/client'
import type { Analytics } from '../api/types'

export default function EstimationDashboard() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    getAnalytics()
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

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
    <div className="flex-1">
      <Topbar title="Estimation Dashboard" subtitle="Overview of every estimation you've created." />
      <div className="p-8 space-y-6">
        <div className="flex justify-end">
          <button
            onClick={() => navigate('/estimation/new')}
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
              <HeroStat tone="coral" label="Total Project Value" value={inr(data.total_project_value)} sub="All estimations" />
              <HeroStat tone="mint" label="Average Estimation" value={inr(data.average_estimation_value)} sub="Per project" />
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
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.recent.map((e) => (
                      <tr key={e.base_name} className="hover:bg-slate-50 cursor-pointer" onClick={() => navigate(`/estimation/${e.base_name}`)}>
                        <td className="py-2.5 pr-4 text-slate-700">{e.client_name}</td>
                        <td className="py-2.5 pr-4 text-slate-600 truncate max-w-[220px]">{e.project_name}</td>
                        <td className="py-2.5 pr-4 font-medium text-slate-800 tabular-nums">
                          {e.grand_total != null ? inr(e.grand_total) : '—'}
                        </td>
                        <td className="py-2.5 pr-4 text-slate-400 text-xs">{new Date(e.modified).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
