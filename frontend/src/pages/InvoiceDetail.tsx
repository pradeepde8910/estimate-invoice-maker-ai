import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import HtmlFrame from '../components/HtmlFrame'
import { inr } from '../components/EstimationResult'
import {
  getEstimationData,
  getInvoice,
  generateInvoice,
  updateDocumentContent,
  updateInvoiceStatus,
  documentPdfUrl,
} from '../api/client'
import type { InvoiceMeta, InvoiceStatus } from '../api/types'

const STATUSES: InvoiceStatus[] = ['Draft', 'Sent', 'Paid', 'Overdue', 'Cancelled']
const STATUS_TONE: Record<InvoiceStatus, string> = {
  Draft: 'bg-slate-100 text-slate-600',
  Sent: 'bg-brand-50 text-brand-700',
  Paid: 'bg-brand-100 text-brand-700',
  Overdue: 'bg-coral-100 text-coral-700',
  Cancelled: 'bg-slate-100 text-slate-400',
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
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      const r = await updateInvoiceStatus(baseName, status)
      setInvoiceMeta(r.invoice_meta)
      setInvoiceHtml(r.invoice_html)
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function saveEdit() {
    if (!baseName) return
    setSaving(true)
    setError(null)
    try {
      await updateDocumentContent(baseName, 'invoice', draft)
      setInvoiceHtml(draft)
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

  return (
    <div className="flex-1">
      <Topbar title="Invoice" subtitle={`${clientName} · ${projectName}`} />
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
                  value={taxPct}
                  onChange={(e) => setTaxPct(Number(e.target.value))}
                  className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-600">Due in (days)</label>
                <input
                  type="number"
                  min={1}
                  value={dueDays}
                  onChange={(e) => setDueDays(Number(e.target.value))}
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
                  onChange={(e) => handleStatusChange(e.target.value as InvoiceStatus)}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-full border-none focus:outline-none focus:ring-2 focus:ring-brand-300 ${
                    STATUS_TONE[invoiceMeta?.status ?? 'Draft']
                  }`}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setInvoiceHtml(null)}
                  className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50"
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
                    onClick={() => {
                      setDraft(invoiceHtml)
                      setEditing(true)
                    }}
                    className="text-sm font-medium bg-white shadow-card px-4 py-2 rounded-full text-slate-600 hover:bg-slate-50"
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
                  <a
                    href={documentPdfUrl(baseName, 'invoice')}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white px-5 py-2.5 rounded-full"
                  >
                    ⬇ PDF
                  </a>
                )}
              </div>
            </div>
            {editing ? (
              <Card>
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={30}
                  className="w-full font-mono text-xs border border-slate-200 rounded-2xl p-4 focus:outline-none focus:ring-2 focus:ring-brand-300 resize-y"
                />
              </Card>
            ) : (
              <div className="rounded-3xl overflow-hidden shadow-card">
                <HtmlFrame html={invoiceHtml} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
