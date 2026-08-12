import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ConfirmModal from '../components/ConfirmModal'
import { inr } from '../components/EstimationResult'
import { listClients, deleteEstimation, ApiError } from '../api/client'
import type { ClientGroup, DocumentSummary } from '../api/types'

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
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  function refresh() {
    return listClients()
      .then((r) => setClients(r.clients))
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
      await refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="flex-1">
      <Topbar showBack title="Estimations" subtitle="Every estimation, grouped by client." />
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
                      <div className="w-full flex items-center justify-between py-3 px-3 -mx-3 rounded-xl hover:bg-slate-50 transition-colors">
                        <span className="text-sm font-medium text-slate-700 text-left truncate max-w-md">
                          {e.project_name}
                        </span>
                        <div className="flex items-center gap-3 shrink-0">
                          {e.grand_total != null && (
                            <span className="text-sm font-semibold text-slate-800 tabular-nums">{inr(e.grand_total)}</span>
                          )}
                          {e.has_invoice && (
                            <span className="text-[11px] font-medium bg-brand-50 text-brand-600 px-2 py-1 rounded-full">Invoiced</span>
                          )}
                          <div className="flex items-center gap-1 ml-2">
                            <button
                              onClick={() => navigate(`/estimation/${e.base_name}`)}
                              className="text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 hover:text-brand-700 px-4 py-2 rounded-full transition-colors"
                            >
                              View
                            </button>
                            <button
                              onClick={(ev) => {
                                ev.stopPropagation()
                                setDeleteTarget(e)
                              }}
                              title="Delete Estimation"
                              className="w-8 h-8 rounded-full text-slate-300 hover:text-coral-600 hover:bg-coral-50 flex items-center justify-center transition-colors ml-1"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M3 6h18"></path>
                                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )}
      </div>



      <ConfirmModal
        isOpen={deleteTarget !== null}
        title="Remove this estimation?"
        message={`This will remove "${deleteTarget?.project_name ?? ''}" from the list. This cannot be undone.`}
        confirmText={deleting ? 'Removing…' : 'Remove'}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}


