import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import StatCard from '../components/StatCard'
import HeroStat from '../components/HeroStat'
import DonutChart from '../components/DonutChart'
import ConfirmModal from '../components/ConfirmModal'
import { inr, compactInr } from '../components/EstimationResult'
import { getAnalytics, deleteInvoice } from '../api/client'
import type { Analytics, DocumentSummary } from '../api/types'

export default function InvoiceDashboard() {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  function refresh() {
    getAnalytics()
      .then(setData)
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
      await deleteInvoice(deleteTarget.invoice_meta.invoice_number)
      setDeleteTarget(null)
      refresh()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  const invoicedRecent = data?.recent_invoices ?? []

  return (
    <div className="flex-1">
      <Topbar showBack title="Invoice Dashboard" subtitle="Revenue and payment status across every invoice." />
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
        {!data ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
              <HeroStat tone="mint" label="Revenue (Paid)" value={compactInr(data.revenue_paid)} sub="Collected" />
              <HeroStat tone="coral" label="Revenue (Pending)" value={compactInr(data.revenue_pending)} sub="Awaiting payment" />
              <Card className="flex flex-col justify-center">
                <StatCard label="Invoiced" value={data.invoiced_count} sub="Estimations" />
              </Card>
              <Card className="flex flex-col justify-center">
                <StatCard label="Total Estimations" value={data.total_estimations} sub="All time" />
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card title="Recent Invoices" className="lg:col-span-2">
                {invoicedRecent.length === 0 ? (
                  <p className="text-sm text-slate-400 py-6 text-center">No invoices generated yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-400 uppercase tracking-wide">
                          <th className="py-2 pr-4">Client</th>
                          <th className="py-2 pr-4">Invoice</th>
                          <th className="py-2 pr-4">Total Due</th>
                          <th className="py-2 pr-4">Status</th>
                          <th className="py-2 pr-4 w-10"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {invoicedRecent.map((e) => (
                          <tr key={e.base_name} className="hover:bg-slate-50">
                            <td className="py-2.5 pr-4 text-slate-700">{e.client_name}</td>
                            <td className="py-2.5 pr-4 text-slate-500 text-xs">{e.invoice_meta?.invoice_number}</td>
                            <td className="py-2.5 pr-4 font-medium text-slate-800 tabular-nums">
                              {e.invoice_meta ? inr(e.invoice_meta.total_due) : '—'}
                            </td>
                            <td className="py-2.5 pr-4">
                              <span className="text-xs font-medium bg-slate-50 px-2 py-1 rounded-full text-slate-500">
                                {e.invoice_meta?.status ?? 'Draft'}
                              </span>
                            </td>
                            <td className="py-2.5 pr-4 text-right flex items-center justify-end gap-1">
                              <button
                                onClick={() => navigate(`/invoice/${e.base_name}`)}
                                className="text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 hover:text-brand-700 px-3 py-1.5 rounded-full transition-colors mr-1"
                              >
                                View
                              </button>
                              <button
                                onClick={(ev) => {
                                  ev.stopPropagation()
                                  setDeleteTarget(e)
                                }}
                                title="Delete Invoice"
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
                )}
                <button onClick={() => navigate('/invoice/list')} className="mt-4 text-xs font-medium text-brand-600 hover:underline">
                  View all →
                </button>
              </Card>
              <Card title="Status Overview">
                <DonutChart 
                  data={Object.entries(data.status_overview).map(([name, value]) => ({ name, value }))} 
                  layout="vertical"
                  valueLabel="Count"
                />
              </Card>
            </div>
          </>
        )}
      </div>

      <ConfirmModal
        isOpen={deleteTarget !== null}
        title="Delete this invoice?"
        message={`This will permanently delete invoice ${deleteTarget?.invoice_meta?.invoice_number ?? ''}. The associated estimation will be reverted to 'Approved' status so you can generate a new invoice if needed.`}
        confirmText={deleting ? 'Deleting…' : 'Delete'}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
