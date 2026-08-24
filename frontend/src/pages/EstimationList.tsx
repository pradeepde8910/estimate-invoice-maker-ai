import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ConfirmModal from '../components/ConfirmModal'
import { inr } from '../components/EstimationResult'
import { listDocuments, deleteEstimation } from '../api/client'
import type { DocumentSummary } from '../api/types'

function filterDocuments(docs: DocumentSummary[], query: string): DocumentSummary[] {
  const q = query.trim().toLowerCase()
  if (!q) return docs
  return docs.filter(
    (d) => d.project_name.toLowerCase().includes(q) || d.client_name.toLowerCase().includes(q)
  )
}

function formatModified(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function EstimationList() {
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null)
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  function refresh() {
    return listDocuments()
      .then((r) => setDocuments(r.documents))
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

  const visible = documents ? filterDocuments(documents, search) : []

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Topbar showBack title="Estimations" subtitle="Every estimation, newest first." />
      <div className="p-8 space-y-6">
        <div className="flex items-center justify-end">
          {documents && documents.length > 0 && (
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by client or project…"
              className="w-64 bg-white shadow-card rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
          )}
        </div>

        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}
        {!documents ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : documents.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">No estimations yet — start one above.</Card>
        ) : visible.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">No estimations match "{search}".</Card>
        ) : (
          <Card className="!p-0 overflow-hidden">
            <ul className="divide-y divide-slate-100">
              {visible.map((d) => (
                <li key={d.base_name}>
                  <div className="w-full flex items-center justify-between py-4 px-5 hover:bg-slate-50 transition-colors">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-slate-800 truncate">{d.project_name}</div>
                      <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                        <span className="truncate">{d.client_name}</span>
                        <span>·</span>
                        <span className="shrink-0">{formatModified(d.modified)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-4">
                      {d.grand_total != null && (
                        <span className="text-sm font-semibold text-slate-800 tabular-nums">{inr(d.grand_total)}</span>
                      )}
                      {d.has_invoice && (
                        <span className="text-[11px] font-medium bg-brand-50 text-brand-600 px-2 py-1 rounded-full">Invoiced</span>
                      )}
                      <div className="flex items-center gap-1 ml-2">
                        <button
                          onClick={() => navigate(`/estimation/${d.base_name}`)}
                          className="text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 hover:text-brand-700 px-4 py-2 rounded-full transition-colors"
                        >
                          View
                        </button>
                        <button
                          onClick={(ev) => {
                            ev.stopPropagation()
                            setDeleteTarget(d)
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
