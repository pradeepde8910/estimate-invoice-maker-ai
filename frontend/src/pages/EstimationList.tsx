import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ConfirmModal from '../components/ConfirmModal'
import LoadingState from '../components/LoadingState'
import { inr } from '../components/EstimationResult'
import { listDocuments, deleteEstimation } from '../api/client'
import type { DocumentSummary } from '../api/types'

type SortField = 'modified' | 'value' | 'project' | 'client'
type SortDir = 'asc' | 'desc'

function filterDocuments(docs: DocumentSummary[], query: string, statusFilter: string): DocumentSummary[] {
  const q = query.trim().toLowerCase()
  return docs.filter((d) => {
    const matchesSearch = !q || (d.project_name || '').toLowerCase().includes(q) || (d.client_name || '').toLowerCase().includes(q)
    const matchesStatus = !statusFilter || d.status === statusFilter
    return matchesSearch && matchesStatus
  })
}

function formatModified(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === 'Approved' ? 'bg-emerald-50 text-emerald-700' :
    status === 'Converted' ? 'bg-indigo-50 text-indigo-700' :
    status === 'Sent' ? 'bg-blue-50 text-blue-700' :
    status === 'Rejected' ? 'bg-coral-50 text-coral-600' :
    'bg-slate-100 text-slate-600'
  return <span className={`text-[11px] font-medium px-2 py-1 rounded-full whitespace-nowrap ${tone}`}>{status}</span>
}

export default function EstimationList() {
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortField, setSortField] = useState<SortField>('modified')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  function refresh() {
    return listDocuments()
      .then((r) => setDocuments(r.documents))
      .catch((e) => toast.error(e.message))
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteEstimation(deleteTarget.base_name)
      setDeleteTarget(null)
      await refresh()
    } catch (e: any) {
      toast.error(e.message)
    } finally {
      setDeleting(false)
    }
  }

  const distinctStatuses = useMemo(() => {
    if (!documents) return []
    return Array.from(new Set(documents.map(d => d.status).filter(Boolean))).sort() as string[]
  }, [documents])

  const visible = useMemo(() => {
    if (!documents) return []
    let filtered = filterDocuments(documents, search, statusFilter)
    filtered = [...filtered].sort((a, b) => {
      let cmp = 0
      if (sortField === 'modified') {
        cmp = new Date(a.modified).getTime() - new Date(b.modified).getTime()
      } else if (sortField === 'value') {
        cmp = (a.grand_total || 0) - (b.grand_total || 0)
      } else if (sortField === 'project') {
        cmp = (a.project_name || '').localeCompare(b.project_name || '')
      } else if (sortField === 'client') {
        cmp = (a.client_name || '').localeCompare(b.client_name || '')
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
    return filtered
  }, [documents, search, statusFilter, sortField, sortDir])

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-1 text-slate-300">↕</span>
    return <span className="ml-1 text-brand-500">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar title="Estimations" subtitle="Every estimation, sortable and filterable." />
      <div className="p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {distinctStatuses.length > 0 && (
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-white shadow-card rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300 cursor-pointer border border-transparent"
              >
                <option value="">All Statuses</option>
                {distinctStatuses.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            )}
          </div>
          {documents && documents.length > 0 && (
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by client or project…"
              className="w-64 bg-white shadow-card rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
          )}
        </div>

        {!documents ? (
          <LoadingState />
        ) : documents.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">No estimations yet — start one above.</Card>
        ) : visible.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">No estimations match your filters.</Card>
        ) : (
          <Card className="!p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 text-xs uppercase tracking-wider">
                    <th className="py-3 px-5 font-medium cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('project')}>
                      Project <SortIcon field="project" />
                    </th>
                    <th className="py-3 px-5 font-medium cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('client')}>
                      Client <SortIcon field="client" />
                    </th>
                    <th className="py-3 px-5 font-medium cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('modified')}>
                      Last Updated <SortIcon field="modified" />
                    </th>
                    <th className="py-3 px-5 font-medium text-right cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('value')}>
                      Value <SortIcon field="value" />
                    </th>
                    <th className="py-3 px-5 font-medium">Status</th>
                    <th className="py-3 px-5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {visible.map((d) => (
                    <tr key={d.base_name} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-800 max-w-[280px] truncate" title={d.project_name}>
                        {d.project_name}
                      </td>
                      <td className="py-3.5 px-5 text-slate-600 max-w-[200px] truncate" title={d.client_name}>
                        {d.client_name || <span className="text-slate-300 italic">Unspecified</span>}
                      </td>
                      <td className="py-3.5 px-5 text-slate-500 text-xs whitespace-nowrap">{formatModified(d.modified)}</td>
                      <td className="py-3.5 px-5 text-right font-semibold text-slate-800 tabular-nums whitespace-nowrap">
                        {d.grand_total != null ? inr(d.grand_total) : '—'}
                      </td>
                      <td className="py-3.5 px-5">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {d.status && <StatusBadge status={d.status} />}
                          {d.has_invoice && (
                            <span className="text-[11px] font-medium bg-brand-50 text-brand-600 px-2 py-1 rounded-full whitespace-nowrap">Invoiced</span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {d.converted_project_id && (
                            <button
                              onClick={() => navigate(`/invoice/projects/${d.converted_project_id}`)}
                              title="Go to the project this estimation was converted into"
                              className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-4 py-2 rounded-full transition-colors whitespace-nowrap"
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="2" y="7" width="20" height="14" rx="2"></rect>
                                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                              </svg>
                              View Project
                            </button>
                          )}
                          <button
                            onClick={() => navigate(`/estimation/${d.base_name}`)}
                            title="View this estimation's details"
                            className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 border border-brand-200 bg-white hover:bg-brand-50 px-4 py-2 rounded-full transition-colors"
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                              <path d="M14 2v6h6"></path>
                            </svg>
                            View Estimation
                          </button>
                          <button
                            onClick={(ev) => {
                              ev.stopPropagation()
                              setDeleteTarget(d)
                            }}
                            title="Delete Estimation"
                            className="w-8 h-8 rounded-full text-slate-300 hover:text-coral-600 hover:bg-coral-50 flex items-center justify-center transition-colors shrink-0"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M3 6h18"></path>
                              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

