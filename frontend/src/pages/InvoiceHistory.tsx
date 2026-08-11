import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { inr } from '../components/EstimationResult'
import ConfirmModal from '../components/ConfirmModal'
import { listClients, deleteInvoice } from '../api/client'
import type { ClientGroup, DocumentSummary } from '../api/types'

export default function InvoiceHistory() {
  const [clients, setClients] = useState<ClientGroup[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  function refresh() {
    listClients()
      .then((r) => setClients(r.clients))
      .catch((e) => setError(e.message))
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleDelete() {
    if (!deleteTarget || !deleteTarget.invoice_meta) return
    setDeleting(true)
    setError(null)
    try {
      await deleteInvoice(deleteTarget.invoice_meta.invoice_id)
      setDeleteTarget(null)
      refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="flex-1">
      <Topbar title="Invoice History" subtitle="Every estimation, ready to be invoiced or already invoiced." />
      <div className="p-8 space-y-6">
        <div className="flex justify-end">
          <button
            onClick={() => navigate('/invoice/new')}
            className="text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white px-5 py-2.5 rounded-full"
          >
            + New Invoice
          </button>
        </div>

        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}
        {!clients ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : clients.length === 0 ? (
          <Card className="text-center py-16">
            <div className="text-4xl mb-3">🧾</div>
            <p className="text-slate-500">No estimations yet. Run an Estimation first, or create a manual invoice above.</p>
            <button
              onClick={() => navigate('/estimation/new')}
              className="mt-5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-5 py-2.5 rounded-full"
            >
              Go to Estimation
            </button>
          </Card>
        ) : (
          <div className="space-y-5">
            {clients.map((c) => (
              <Card key={c.client_name}>
                <h3 className="font-semibold text-slate-800 mb-2">{c.client_name}</h3>
                <ul className="divide-y divide-slate-100">
                  {c.estimations.map((e) => (
                    <li key={e.base_name} className="flex items-center justify-between py-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-slate-700 truncate">{e.project_name}</div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {e.grand_total != null ? inr(e.grand_total) : '—'}
                          {e.invoice_meta && ` · ${e.invoice_meta.invoice_number}`}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {e.has_invoice && (
                          <span className="text-[11px] font-medium bg-brand-50 text-brand-600 px-2.5 py-1 rounded-full">
                            {e.invoice_meta?.status ?? 'Invoiced'}
                          </span>
                        )}
                        <button
                          onClick={() => navigate(`/invoice/${e.base_name}`)}
                          className="text-sm font-medium bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-600 px-4 py-2 rounded-full"
                        >
                          {e.has_invoice ? 'View Invoice' : 'Generate Invoice'}
                        </button>
                        {e.has_invoice && (
                          <button
                            onClick={(ev) => {
                              ev.stopPropagation()
                              setDeleteTarget(e)
                            }}
                            title="Delete Invoice"
                            className="w-8 h-8 rounded-full text-slate-300 hover:text-coral-600 hover:bg-coral-50 flex items-center justify-center transition-colors"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M3 6h18"></path>
                              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                            </svg>
                          </button>
                        )}
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
        title="Delete this invoice?"
        message={`This will permanently delete invoice ${deleteTarget?.invoice_meta?.invoice_number ?? ''}. The associated estimation will be reverted to 'Approved' status.`}
        confirmText={deleting ? 'Deleting…' : 'Delete'}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
