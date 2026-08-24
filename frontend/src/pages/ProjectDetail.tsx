import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ConfirmModal from '../components/ConfirmModal'
import RecordPaymentModal from '../components/RecordPaymentModal'
import { getProjectSummary, listInvoices, updateInvoiceStatusV2, downloadInvoiceStatement } from '../api/client'

function currentMonthValue(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function monthToDateRange(monthValue: string): { from: string; to: string } {
  const [year, month] = monthValue.split('-').map(Number)
  const from = `${year}-${String(month).padStart(2, '0')}-01`
  const lastDay = new Date(year, month, 0).getDate()
  const to = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  return { from, to }
}

function paymentStatusBadge(status: string) {
  const tone =
    status === 'PAID' ? 'bg-emerald-50 text-emerald-700' :
    status === 'PARTIALLY_PAID' ? 'bg-amber-50 text-amber-700' :
    'bg-slate-100 text-slate-500'
  const label = status === 'PARTIALLY_PAID' ? 'Partially Paid' : status.charAt(0) + status.slice(1).toLowerCase()
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{label}</span>
}

export default function ProjectDetail() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<any>(null)
  const [invoices, setInvoices] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statementMonth, setStatementMonth] = useState(currentMonthValue())
  const [statementFormat, setStatementFormat] = useState<'pdf' | 'excel' | 'csv'>('pdf')
  const [downloadingStatement, setDownloadingStatement] = useState(false)
  const [success, setSuccess] = useState<string | null>(null)

  const [invoiceToIssue, setInvoiceToIssue] = useState<any | null>(null)
  const [invoiceToPay, setInvoiceToPay] = useState<any | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  function loadData() {
    if (!projectId) return
    Promise.all([
      getProjectSummary(projectId),
      listInvoices(projectId)
    ]).then(([sum, inv]) => {
      setSummary(sum)
      setInvoices(inv)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  async function handleDownloadStatement() {
    if (!projectId) return
    const { from, to } = monthToDateRange(statementMonth)
    setDownloadingStatement(true)
    setError(null)
    try {
      await downloadInvoiceStatement(from, to, { projectId, format: statementFormat })
    } catch (e: any) {
      setError(e.message || 'Failed to download statement')
    } finally {
      setDownloadingStatement(false)
    }
  }

  async function confirmIssue() {
    if (!invoiceToIssue) return
    setActionLoading(true)
    setError(null)
    try {
      await updateInvoiceStatusV2(invoiceToIssue.id, 'ISSUED')
      loadData()
      setSuccess(`Invoice ${invoiceToIssue.invoice_number || ''} issued.`)
      setInvoiceToIssue(null)
    } catch (e: any) {
      setError(e.message || 'Failed to issue invoice')
    } finally {
      setActionLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [projectId])

  useEffect(() => {
    if (!success) return
    const t = setTimeout(() => setSuccess(null), 4000)
    return () => clearTimeout(t)
  }, [success])

  if (loading) return <div className="p-8 text-center text-slate-500">Loading project details...</div>
  if (!summary) return <div className="p-8 text-center text-red-500">Failed to load project.</div>

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Topbar showBack title={summary.project_name} subtitle={`Project No: ${summary.project_number}`} />
      <div className="p-8 space-y-6 max-w-6xl mx-auto">
        
        {error && <div className="p-4 bg-coral-50 text-coral-600 rounded-lg">{error}</div>}
        {success && <div className="p-4 bg-brand-50 text-brand-700 rounded-lg">{success}</div>}

        {/* Financial Summary */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card title="Contract Value" className="bg-white">
            <div className="text-2xl font-semibold tracking-tight text-slate-800">₹{parseFloat(summary.financials.contract_value).toLocaleString('en-IN')}</div>
          </Card>
          <Card title="Total Billed" className="bg-white">
            <div className="text-2xl font-semibold tracking-tight text-blue-600">₹{parseFloat(summary.financials.total_billed).toLocaleString('en-IN')}</div>
          </Card>
          <Card title="Total Paid" className="bg-white">
            <div className="text-2xl font-semibold tracking-tight text-emerald-600">₹{parseFloat(summary.financials.total_paid).toLocaleString('en-IN')}</div>
          </Card>
          <Card title="Remaining Contract" className="bg-white">
            <div className="text-2xl font-semibold tracking-tight text-amber-600">₹{parseFloat(summary.financials.remaining_contract).toLocaleString('en-IN')}</div>
          </Card>
          <Card title="Reserved Contingency" className="bg-white">
            <div className="text-2xl font-semibold tracking-tight text-purple-600">₹{parseFloat(summary.financials.reserved_contingency).toLocaleString('en-IN')}</div>
          </Card>
        </div>

        {/* Commercial Components */}
        <Card title="Commercial Components">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead>
                <tr className="border-b border-slate-100 text-slate-400">
                  <th className="pb-3 font-medium">Component</th>
                  <th className="pb-3 font-medium">Type</th>
                  <th className="pb-3 font-medium">Policy</th>
                  <th className="pb-3 font-medium text-right">Amount</th>
                  <th className="pb-3 font-medium text-right">Billed</th>
                  <th className="pb-3 font-medium text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {summary.components && summary.components.map((comp: any) => (
                  <tr key={comp.id}>
                    <td className="py-3 font-medium text-slate-900">{comp.name}</td>
                    <td className="py-3 capitalize">{comp.component_type}</td>
                    <td className="py-3 capitalize">{comp.billing_policy}</td>
                    <td className="py-3 text-right">₹{parseFloat(comp.amount).toLocaleString('en-IN')}</td>
                    <td className="py-3 text-right">₹{parseFloat(comp.billed_amount).toLocaleString('en-IN')}</td>
                    <td className="py-3 text-center">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        comp.status === 'RESERVED' ? 'bg-purple-50 text-purple-700' :
                        comp.status === 'AVAILABLE' ? 'bg-emerald-50 text-emerald-700' :
                        'bg-slate-100 text-slate-600'
                      }`}>
                        {comp.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {(!summary.components || summary.components.length === 0) && (
                  <tr><td colSpan={6} className="py-8 text-center text-slate-400">No commercial components found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Invoices List */}
        <Card title="Invoices">
          <div className="flex justify-between items-center mb-4 flex-wrap gap-3">
            <h3 className="text-sm font-medium text-slate-700">All Invoices</h3>
            <div className="flex items-center gap-2">
              <input
                type="month"
                value={statementMonth}
                onChange={(e) => setStatementMonth(e.target.value)}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5"
              />
              <select
                value={statementFormat}
                onChange={(e) => setStatementFormat(e.target.value as 'pdf' | 'excel' | 'csv')}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5"
              >
                <option value="pdf">PDF</option>
                <option value="excel">Excel</option>
                <option value="csv">CSV</option>
              </select>
              <button
                onClick={handleDownloadStatement}
                disabled={downloadingStatement}
                title="Download a combined statement of every invoice raised in this project during the selected month"
                className="text-xs font-medium bg-white border border-slate-200 text-slate-700 px-3 py-1.5 rounded-full hover:bg-slate-50 disabled:opacity-50"
              >
                {downloadingStatement ? 'Preparing…' : 'Download Monthly Statement'}
              </button>
              <button
                onClick={() => navigate(`/invoice/projects/${projectId}/new-invoice`)}
                className="text-xs font-medium bg-brand-50 text-brand-700 px-3 py-1.5 rounded-full hover:bg-brand-100"
              >
                + Create Invoice
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead>
                <tr className="border-b border-slate-100 text-slate-400">
                  <th className="pb-3 font-medium">Invoice No</th>
                  <th className="pb-3 font-medium">Date</th>
                  <th className="pb-3 font-medium">Billing</th>
                  <th className="pb-3 font-medium">Amount</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {invoices.map(inv => (
                  <tr key={inv.id}>
                    <td className="py-3 font-medium">{inv.invoice_number || <span className="text-slate-400 italic">Draft</span>}</td>
                    <td className="py-3">{new Date(inv.invoice_date || inv.created_at).toLocaleDateString()}</td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {inv.billing_model && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide bg-indigo-50 text-indigo-700">
                            {inv.billing_model}
                          </span>
                        )}
                        {(inv.billing_sources || []).map((src: string) => (
                          <span key={src} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">
                            {src}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3">
                      <div className="font-medium text-slate-900">₹{parseFloat(inv.total_payable).toLocaleString('en-IN')}</div>
                      {(inv.payment_status === 'PARTIALLY_PAID' || inv.payment_status === 'PAID') && parseFloat(inv.amount_paid || 0) > 0 && (
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          ₹{parseFloat(inv.amount_paid).toLocaleString('en-IN')} paid
                          {parseFloat(inv.balance_due || 0) > 0 && <> · ₹{parseFloat(inv.balance_due).toLocaleString('en-IN')} due</>}
                        </div>
                      )}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-col gap-1 items-start">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          inv.status === 'ISSUED' ? 'bg-blue-50 text-blue-700' :
                          inv.status === 'CANCELLED' ? 'bg-coral-50 text-coral-600' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {inv.status}
                        </span>
                        {inv.status !== 'DRAFT' && paymentStatusBadge(inv.payment_status || 'UNPAID')}
                      </div>
                    </td>
                    <td className="py-3 text-right space-x-3">
                       <button onClick={() => navigate(`/invoice/projects/${projectId}/invoice/${inv.id}`)} className="text-slate-600 hover:underline text-xs font-medium">View</button>
                       {inv.status === 'DRAFT' && (
                         <button
                           title="Finalize this draft invoice to lock its details. Once issued, it cannot be modified."
                           onClick={() => setInvoiceToIssue(inv)}
                           disabled={actionLoading}
                           className="text-blue-600 hover:underline text-xs font-medium inline-flex items-center gap-1 disabled:opacity-50 disabled:no-underline"
                         >
                           Issue ⓘ
                         </button>
                       )}
                       {inv.status === 'ISSUED' && inv.payment_status !== 'PAID' && (
                         <button
                           title="Record a payment received against this invoice — full or partial."
                           onClick={() => setInvoiceToPay(inv)}
                           className="text-emerald-600 hover:underline text-xs font-medium inline-flex items-center gap-1"
                         >
                           Record Payment ⓘ
                         </button>
                       )}
                    </td>
                  </tr>
                ))}
                {invoices.length === 0 && (
                  <tr><td colSpan={6} className="py-8 text-center text-slate-400">No invoices found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <ConfirmModal
        isOpen={invoiceToIssue !== null}
        title="Issue this invoice?"
        message={
          <>
            This will finalize <strong>{invoiceToIssue?.invoice_number || 'this draft invoice'}</strong> (₹
            {invoiceToIssue ? parseFloat(invoiceToIssue.total_payable).toLocaleString('en-IN') : ''}) and lock its
            details. Once issued, it cannot be modified.
          </>
        }
        confirmText={actionLoading ? 'Issuing…' : 'Issue Invoice'}
        busy={actionLoading}
        onConfirm={confirmIssue}
        onCancel={() => setInvoiceToIssue(null)}
      />

      {invoiceToPay && projectId && (
        <RecordPaymentModal
          projectId={projectId}
          invoice={invoiceToPay}
          onClose={() => setInvoiceToPay(null)}
          onRecorded={(message) => {
            loadData()
            setSuccess(message)
            setInvoiceToPay(null)
          }}
        />
      )}
    </div>
  )
}
