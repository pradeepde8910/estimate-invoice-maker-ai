import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ConfirmModal from '../components/ConfirmModal'
import HtmlFrame, { type HtmlFrameHandle } from '../components/HtmlFrame'
import { inr } from '../components/EstimationResult'
import {
  getEstimationData,
  getInvoice,
  generateInvoice,
  updateDocumentContent,
  updateInvoiceStatus,
  openDocumentPdf,
} from '../api/client'
import type { InvoiceMeta, InvoiceStatus } from '../api/types'

const STATUSES: InvoiceStatus[] = ['Draft', 'Sent', 'Partially Paid', 'Paid', 'Overdue', 'Cancelled']
const STATUS_TONE: Record<InvoiceStatus, string> = {
  Draft: 'bg-slate-100 text-slate-600',
  Sent: 'bg-blue-100 text-blue-700',
  'Partially Paid': 'bg-yellow-100 text-yellow-800',
  Paid: 'bg-green-100 text-green-700',
  Overdue: 'bg-red-100 text-red-700',
  Cancelled: 'bg-slate-100 text-slate-500',
}

export default function InvoiceDetail() {
  const { baseName } = useParams<{ baseName: string }>()
  const [estimation, setEstimation] = useState<any>(null)
  const [invoiceHtml, setInvoiceHtml] = useState<string | null>(null)
  const [invoiceMeta, setInvoiceMeta] = useState<InvoiceMeta | null>(null)
  const [taxPct, setTaxPct] = useState(18)
  const [dueDays, setDueDays] = useState(15)
  const [generating, setGenerating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingStatus, setPendingStatus] = useState<InvoiceStatus | null>(null)
  const [paymentAmount, setPaymentAmount] = useState<number>(0)
  const [paymentDate, setPaymentDate] = useState<string>(new Date().toISOString().split('T')[0])
  const frameRef = useRef<HtmlFrameHandle>(null)

  useEffect(() => {
    if (!baseName) return
    getEstimationData(baseName).then(setEstimation).catch((e) => setError(e.message))
    getInvoice(baseName)
      .then((r) => {
        setInvoiceHtml(r.invoice_html)
        setInvoiceMeta(r.invoice_meta)
        if (r.invoice_meta) setTaxPct(r.invoice_meta.tax_percentage)
      })
      .catch(() => {})
  }, [baseName])

  async function handleGenerate() {
    if (!baseName) return
    setGenerating(true)
    setError(null)
    try {
      const r = await generateInvoice(baseName, { tax_percentage: taxPct, due_days: dueDays })
      setInvoiceHtml(r.invoice_html)
      setInvoiceMeta(r.invoice_meta)
    } catch (e: any) {
      setError(e.message || 'Failed to generate invoice')
    } finally {
      setGenerating(false)
    }
  }

  async function handleStatusChange(status: InvoiceStatus) {
    if (!baseName) return
    setError(null)
    try {
      let amt: number | undefined
      let dt: string | undefined
      if (status === 'Paid' || status === 'Partially Paid') {
        amt = paymentAmount
        dt = paymentDate
      }
      const r = await updateInvoiceStatus(baseName, status, amt, dt)
      setInvoiceMeta(r.invoice_meta)
      setInvoiceHtml(r.invoice_html)
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function saveEdit() {
    if (!baseName) return
    const edited = frameRef.current?.getHtml()
    if (!edited) return
    setSaving(true)
    setError(null)
    try {
      await updateDocumentContent(baseName, 'invoice', edited)
      setInvoiceHtml(edited)
      setEditing(false)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  function download() {
    if (!invoiceHtml) return
    const blob = new Blob([invoiceHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${invoiceMeta?.invoice_number || baseName}.html`
    a.click()
    URL.revokeObjectURL(url)
  }

  const clientName = estimation?.client_name || estimation?.analysis?.client_name || 'Client'
  const projectName = estimation?.project_name || estimation?.analysis?.project_name || ''
  const grandTotal = estimation?.cost_estimation?.grand_total ?? 0
  
  const isDraft = (invoiceMeta?.status ?? 'Draft') === 'Draft'

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Topbar showBack title="Invoice" subtitle={`${clientName} · ${projectName}`} />
      <div className="p-8 max-w-4xl space-y-6">
        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}

        {!invoiceHtml && (
          <Card title="Generate Invoice">
            <div className="flex items-center justify-between text-sm text-slate-500 mb-4">
              <span>Estimation subtotal</span>
              <span className="font-semibold text-slate-800">{inr(grandTotal)}</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-slate-600">Tax (%)</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={taxPct}
                  onChange={(e) => setTaxPct(Math.min(100, Math.max(0, Number(e.target.value))))}
                  className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-600">Due in (days)</label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={dueDays}
                  onChange={(e) => setDueDays(Math.min(365, Math.max(1, Number(e.target.value))))}
                  className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
              </div>
            </div>

            <Link to="/organization" className="mt-4 inline-block text-sm text-brand-600 hover:underline">
              Edit your company details & branding →
            </Link>

            <button
              disabled={generating}
              onClick={handleGenerate}
              className="mt-6 w-full bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 text-white font-medium py-3 rounded-full"
            >
              {generating ? 'Generating…' : '🧾 Generate Invoice'}
            </button>
          </Card>
        )}

        {invoiceHtml && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500">Status</span>
                <select
                  value={invoiceMeta?.status ?? 'Draft'}
                  onChange={(e) => {
                    const newStatus = e.target.value as InvoiceStatus
                    setPaymentAmount(invoiceMeta?.total_due || grandTotal)
                    setPaymentDate(new Date().toISOString().split('T')[0])
                    if (isDraft && newStatus !== 'Draft') {
                      setPendingStatus(newStatus)
                    } else if (newStatus === 'Paid' || newStatus === 'Partially Paid') {
                      setPendingStatus(newStatus)
                    } else {
                      handleStatusChange(newStatus)
                    }
                  }}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-full border-none focus:outline-none focus:ring-2 focus:ring-brand-300 ${
                    STATUS_TONE[invoiceMeta?.status ?? 'Draft']
                  }`}
                >
                  {STATUSES.filter(s => isDraft || s !== 'Draft').map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3">
                <button
                  disabled={!isDraft}
                  onClick={() => setInvoiceHtml(null)}
                  className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Regenerate
                </button>
                {editing ? (
                  <>
                    <button
                      onClick={() => setEditing(false)}
                      className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50"
                    >
                      Cancel
                    </button>
                    <button
                      disabled={saving}
                      onClick={saveEdit}
                      className="text-sm font-medium bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 text-white px-5 py-2.5 rounded-full"
                    >
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                  </>
                ) : (
                  <button
                    disabled={!isDraft}
                    onClick={() => setEditing(true)}
                    className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    ✎ Edit
                  </button>
                )}
                <button
                  onClick={download}
                  className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50"
                >
                  ⬇ .html
                </button>
                {baseName && (
                  <button
                    onClick={() => openDocumentPdf(baseName, 'invoice').catch((e: any) => setError(e.message))}
                    className="text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white px-5 py-2.5 rounded-full"
                  >
                    ⬇ PDF
                  </button>
                )}
              </div>
            </div>
            {editing && (
              <p className="text-sm text-brand-600 bg-brand-50 rounded-2xl px-4 py-3">
                Click directly into the invoice below to edit it, then press Save.
              </p>
            )}
            <div className="rounded-3xl overflow-hidden shadow-card">
              <HtmlFrame ref={frameRef} html={invoiceHtml} editable={editing} />
            </div>
          </>
        )}
      </div>

      <ConfirmModal
        isOpen={pendingStatus !== null}
        title={pendingStatus === 'Paid' || pendingStatus === 'Partially Paid' ? `Mark as ${pendingStatus}?` : 'Lock Invoice?'}
        message={
          <div className="space-y-4">
            <p>
              {isDraft
                ? `Once you mark this invoice as ${pendingStatus}, it can never be reverted back to Draft. It will be permanently locked from further manual HTML edits.`
                : `You are about to mark this invoice as ${pendingStatus}.`}
            </p>
            {(pendingStatus === 'Paid' || pendingStatus === 'Partially Paid') && (
              <div className="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">Amount Paid (₹)</label>
                  <input
                    type="number"
                    value={paymentAmount}
                    onChange={(e) => setPaymentAmount(Number(e.target.value))}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">Payment Date</label>
                  <input
                    type="date"
                    value={paymentDate}
                    onChange={(e) => setPaymentDate(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                  />
                </div>
              </div>
            )}
          </div>
        }
        confirmText={`Mark as ${pendingStatus}`}
        cancelText="Cancel"
        onConfirm={() => {
          if (pendingStatus) handleStatusChange(pendingStatus)
          setPendingStatus(null)
        }}
        onCancel={() => setPendingStatus(null)}
        onClose={() => setPendingStatus(null)}
      />
    </div>
  )
}
