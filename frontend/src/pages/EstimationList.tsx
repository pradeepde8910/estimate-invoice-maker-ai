import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { inr } from '../components/EstimationResult'
import { listClients } from '../api/client'
import type { ClientGroup } from '../api/types'

function filterClients(clients: ClientGroup[], query: string): ClientGroup[] {
  const q = query.trim().toLowerCase()
  if (!q) return clients
  return clients
    .map((c) => {
      if (c.client_name.toLowerCase().includes(q)) return c
      const estimations = c.estimations.filter((e) => e.project_name.toLowerCase().includes(q))
      return estimations.length ? { ...c, estimations, estimation_count: estimations.length } : null
    })
    .filter((c): c is ClientGroup => c !== null)
}

export default function EstimationList() {
  const [clients, setClients] = useState<ClientGroup[] | null>(null)
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    listClients()
      .then((r) => setClients(r.clients))
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="flex-1">
      <Topbar title="Estimations" subtitle="Every estimation, grouped by client." />
      <div className="p-8 space-y-6">
        <div className="flex items-center justify-end">
          {clients && clients.length > 0 && (
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by client or project…"
              className="w-64 bg-white shadow-card rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
          )}
        </div>

        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}
        {!clients ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : clients.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">No estimations yet — start one above.</Card>
        ) : (
          <div className="space-y-4">
            {filterClients(clients, search).map((c) => (
              <Card key={c.client_name}>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-slate-800">{c.client_name}</h3>
                  <span className="text-xs text-slate-400">
                    {c.estimation_count} estimation{c.estimation_count !== 1 ? 's' : ''}
                  </span>
                </div>
                <ul className="divide-y divide-slate-100">
                  {c.estimations.map((e) => (
                    <li key={e.base_name}>
                      <button
                        onClick={() => navigate(`/estimation/${e.base_name}`)}
                        className="w-full flex items-center justify-between py-3 px-3 -mx-3 rounded-xl hover:bg-slate-50 group transition-colors"
                      >
                        <span className="text-sm font-medium text-slate-700 group-hover:text-brand-700 text-left truncate max-w-md">
                          {e.project_name}
                        </span>
                        <div className="flex items-center gap-3 shrink-0">
                          {e.grand_total != null && (
                            <span className="text-sm font-semibold text-slate-800 tabular-nums">{inr(e.grand_total)}</span>
                          )}
                          {e.has_invoice && (
                            <span className="text-[11px] font-medium bg-brand-50 text-brand-600 px-2 py-1 rounded-full">Invoiced</span>
                          )}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
