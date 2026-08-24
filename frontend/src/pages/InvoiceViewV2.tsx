import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import RecordPaymentModal from '../components/RecordPaymentModal'
import { getInvoiceDetails, downloadInvoicePdf, getOrganization } from '../api/client'
import type { OrganizationProfile } from '../api/types'

export default function InvoiceViewV2() {
  const { projectId, invoiceId } = useParams()
  const navigate = useNavigate()
  const [invoice, setInvoice] = useState<any>(null)
  const [org, setOrg] = useState<OrganizationProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [showPaymentModal, setShowPaymentModal] = useState(false)
  const [paymentSuccess, setPaymentSuccess] = useState<string | null>(null)

  function reloadInvoice() {
    if (invoiceId) getInvoiceDetails(invoiceId).then(setInvoice).catch(() => {})
  }

  async function handleDownload() {
    if (!invoiceId) return
    setDownloading(true)
    setDownloadError(null)
    try {
      await downloadInvoicePdf(invoiceId)
    } catch (e: any) {
      setDownloadError(e.message || 'Failed to download PDF')
    } finally {
      setDownloading(false)
    }
  }

  useEffect(() => {
    if (invoiceId) {
      getInvoiceDetails(invoiceId)
        .then(setInvoice)
        .catch(e => setError(e.message))
        .finally(() => setLoading(false))
    }
    getOrganization().then((r) => setOrg(r.profile)).catch(() => setOrg(null))
  }, [invoiceId])

  useEffect(() => {
    if (!paymentSuccess) return
    const t = setTimeout(() => setPaymentSuccess(null), 4000)
    return () => clearTimeout(t)
  }, [paymentSuccess])

  if (loading) return <div className="p-8 text-center text-slate-500">Loading invoice...</div>
  if (error || !invoice) return <div className="p-8 text-center text-red-500">{error || 'Failed to load invoice.'}</div>

  const formatMoney = (val: string | number) => `₹${parseFloat(val.toString()).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`

  // Group items by milestone and requirement
  const groupedItems = invoice.items?.reduce((acc: any, item: any) => {
    const groupId = item.milestone_id || (item.component_id ? `comp_${item.component_id}` : 'other');
    const groupName = item.milestone_name || (item.component_id ? 'Commercial Components' : 'Other Items');
    
    if (!acc[groupId]) {
      acc[groupId] = {
        name: groupName,
        requirements: {},
        total: 0
      };
    }

    const reqName = item.requirement_name || 'General';
    if (!acc[groupId].requirements[reqName]) {
      acc[groupId].requirements[reqName] = {
        name: reqName,
        items: [],
        total: 0
      };
    }

    acc[groupId].requirements[reqName].items.push(item);
    acc[groupId].requirements[reqName].total += parseFloat(item.amount);
    acc[groupId].total += parseFloat(item.amount);
    
    return acc;
  }, {}) || {};

  const hasBankInfo = Boolean(invoice.bank_name || invoice.bank_account_number || invoice.bank_ifsc);

  const isStandalone = invoice.invoice_type === 'STANDALONE' || !invoice.project_id

  return (
    <div className="flex-1 bg-slate-50 min-h-screen pb-12">
      <Topbar showBack title={`Invoice ${invoice.invoice_number || 'Draft'}`} subtitle={invoice.project_name || invoice.client_name} />

      <div className="max-w-4xl mx-auto mt-8 px-4">

        {/* Actions Bar */}
        <div className="flex justify-between items-center mb-4">
          <button
            onClick={() => navigate(isStandalone ? '/invoice' : `/invoice/projects/${projectId}`)}
            className="text-sm font-medium text-slate-600 hover:text-slate-900"
          >
            {isStandalone ? '← Back to Projects & Invoices' : '← Back to Project'}
          </button>
          <div className="flex space-x-3">
            {invoice.status === 'ISSUED' && invoice.payment_status !== 'PAID' && (
              <button
                onClick={() => setShowPaymentModal(true)}
                className="text-sm font-medium bg-white border border-emerald-200 text-emerald-700 px-4 py-2 rounded-lg hover:bg-emerald-50"
              >
                Record Payment
              </button>
            )}
            <button onClick={() => window.print()} className="text-sm font-medium bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-50">
              Print
            </button>
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="text-sm font-medium bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-700 disabled:opacity-50 inline-flex items-center gap-2"
            >
              {downloading ? 'Preparing…' : 'Download Statement (PDF)'}
            </button>
          </div>
        </div>

        {paymentSuccess && (
          <div className="mb-4 text-sm text-brand-700 bg-brand-50 rounded-lg px-4 py-2">{paymentSuccess}</div>
        )}

        {downloadError && (
          <div className="mb-4 text-sm text-coral-600 bg-coral-50 rounded-lg px-4 py-2">{downloadError}</div>
        )}

        {/* Invoice Paper */}
        <div className="bg-white shadow-xl rounded border border-slate-200">

          <div className="p-8">

            {/* Seller Block */}
            <div className="flex justify-between items-start mb-4 pb-4 border-b border-slate-100">
              <div className="flex items-start gap-3">
                {org?.logo_path && (
                  <img src={`/branding/${org.logo_path}`} alt={org.name} className="h-10 w-auto object-contain" />
                )}
                <div>
                  <div className="text-base font-black text-slate-900 tracking-tight">{org?.name?.toUpperCase() || 'YOUR COMPANY'}</div>
                  {org?.tagline && <div className="text-[11px] font-semibold text-brand-600 uppercase tracking-wide">{org.tagline}</div>}
                  <div className="text-xs text-slate-500 mt-0.5 max-w-sm">
                    {org?.address}
                    {(org?.phone || org?.email) && (
                      <div>{org?.phone}{org?.phone && org?.email ? ' | ' : ''}{org?.email}</div>
                    )}
                  </div>
                </div>
              </div>
              {org?.gstin && (
                <div className="text-xs text-slate-500 text-right shrink-0 pl-6">GSTIN: <span className="font-medium text-slate-700">{org.gstin}</span></div>
              )}
            </div>

            {/* Header Block */}
            <div className="flex justify-between items-start mb-6 border-b-2 border-slate-900 pb-4">
              <div>
                <h3 className="text-xl font-bold tracking-tight text-slate-900 leading-tight">
                  {invoice.project_name || invoice.client_name}
                </h3>
                <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500 mt-1">
                  {invoice.project_number && <span>Project ID: <span className="font-medium text-slate-700">{invoice.project_number}</span></span>}
                  {invoice.project_start_date && <span>Start: <span className="font-medium text-slate-700">{new Date(invoice.project_start_date).toLocaleDateString()}</span></span>}
                  {invoice.project_end_date && <span>End: <span className="font-medium text-slate-700">{new Date(invoice.project_end_date).toLocaleDateString()}</span></span>}
                  {isStandalone && <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold uppercase tracking-wide text-[10px]">Standalone</span>}
                </div>
              </div>

              <div className="text-right shrink-0 pl-6">
                <div className="flex items-center justify-end gap-2 mb-1.5">
                  <h1 className="text-xl font-black text-slate-900 tracking-tight">INVOICE</h1>
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest ${
                    invoice.status === 'ISSUED' ? 'bg-blue-100 text-blue-800' :
                    invoice.status === 'CANCELLED' ? 'bg-coral-100 text-coral-700' :
                    'bg-slate-200 text-slate-700'
                  }`}>
                    {invoice.status}
                  </span>
                  {invoice.status !== 'DRAFT' && (
                    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest ${
                      invoice.payment_status === 'PAID' ? 'bg-emerald-100 text-emerald-800' :
                      invoice.payment_status === 'PARTIALLY_PAID' ? 'bg-amber-100 text-amber-800' :
                      'bg-slate-200 text-slate-700'
                    }`}>
                      {invoice.payment_status === 'PARTIALLY_PAID' ? 'Partially Paid' : invoice.payment_status}
                    </span>
                  )}
                </div>
                <div className="text-sm space-y-0.5">
                  <div><span className="text-slate-500">No.</span> <span className="font-bold text-slate-900">{invoice.invoice_number || 'DRAFT'}</span></div>
                  {invoice.invoice_date && <div><span className="text-slate-500">Date:</span> <span className="font-medium text-slate-800">{new Date(invoice.invoice_date).toLocaleDateString()}</span></div>}
                  {invoice.due_date && <div><span className="text-slate-500">Due:</span> <span className="font-medium text-slate-800">{new Date(invoice.due_date).toLocaleDateString()}</span></div>}
                  {invoice.payment_terms && <div><span className="text-slate-500">Terms:</span> <span className="font-medium text-slate-800">{invoice.payment_terms}</span></div>}
                  {invoice.po_number && <div><span className="text-slate-500">PO No.:</span> <span className="font-medium text-slate-800">{invoice.po_number}</span></div>}
                </div>
              </div>
            </div>

            {/* Items Table */}
            <div className="mb-6">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-900 text-white">
                    <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider w-10">#</th>
                    <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider">{isStandalone ? 'Description' : 'Milestone Details'}</th>
                    <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider w-24">HSN/SAC</th>
                    <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-right w-20">Hours</th>
                    <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-right w-32">Amount Due</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 border-b border-slate-200">
                  {(() => {
                    let sno = 0
                    return Object.values(groupedItems).map((group: any, idx: number) => (
                    <React.Fragment key={idx}>
                      <tr className="bg-slate-50">
                        <td colSpan={5} className="py-1.5 px-3 text-xs font-bold text-slate-800 tracking-widest uppercase border-y border-slate-200">
                          {group.name}
                        </td>
                      </tr>

                      {Object.values(group.requirements).map((reqGroup: any, reqIdx: number) => (
                        <React.Fragment key={reqIdx}>
                          {reqGroup.name !== 'General' && (
                            <tr className="bg-white">
                              <td colSpan={5} className="py-1 px-5 text-[11px] font-bold text-slate-500 tracking-wide">
                                {reqGroup.name}
                              </td>
                            </tr>
                          )}
                          {reqGroup.items.map((item: any) => {
                            sno += 1
                            return (
                            <tr key={item.id} className="hover:bg-slate-50/50">
                              <td className="py-1.5 px-3 text-sm text-slate-500 font-mono">
                                {sno}
                              </td>
                              <td className={`py-1.5 ${reqGroup.name !== 'General' ? 'px-6' : 'px-3'} text-sm text-slate-800`}>
                                {item.description}
                              </td>
                              <td className="py-1.5 px-3 text-xs text-slate-500 font-mono">
                                {item.hsn_sac || '-'}
                              </td>
                              <td className="py-1.5 px-3 text-sm text-slate-600 text-right font-mono">
                                {item.hours ? parseFloat(item.hours).toFixed(1) : '-'}
                              </td>
                              <td className="py-1.5 px-3 text-sm font-medium text-slate-900 text-right">
                                {formatMoney(item.amount)}
                              </td>
                            </tr>
                            )
                          })}
                        </React.Fragment>
                      ))}

                      {group.total > 0 && (
                        <tr>
                          <td colSpan={4} className="py-1.5 px-3 text-xs font-bold text-slate-500 text-right uppercase tracking-wider">Phase Total</td>
                          <td className="py-1.5 px-3 text-sm font-bold text-slate-900 text-right bg-slate-50/50">
                            {formatMoney(group.total)}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                    ))
                  })()}
                </tbody>
              </table>
            </div>

            {/* Bottom Section Grid (Billed To, Payment Info, Financials) */}
            <div className="grid grid-cols-12 gap-4 mb-6 items-start">

              {/* Left Column: Billed To */}
              <div className={hasBankInfo ? 'col-span-5' : 'col-span-7'}>
                <div className="bg-amber-50/50 border border-amber-100 rounded-lg p-4">
                  <h3 className="text-xs font-bold text-amber-800 uppercase tracking-widest mb-2 border-b border-amber-200 pb-1.5">Billed To</h3>
                  <p className="text-sm font-bold text-slate-900">{invoice.client_name}</p>

                  {invoice.client_address && (
                    <p className="text-sm text-slate-600 mt-1 whitespace-pre-line leading-snug">{invoice.client_address}</p>
                  )}

                  <div className="text-sm text-slate-600 mt-1.5 space-y-0.5">
                    {invoice.client_email && (
                      <p><span className="font-medium text-slate-800 mr-1">Email:</span>{invoice.client_email}</p>
                    )}
                    {invoice.client_phone && (
                      <p><span className="font-medium text-slate-800 mr-1">Phone:</span>{invoice.client_phone}</p>
                    )}
                    {invoice.client_gstin && (
                      <p><span className="font-medium text-slate-800 mr-1">GSTIN:</span>{invoice.client_gstin}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Middle Column: Payment Info (omitted entirely when no bank details are configured) */}
              {hasBankInfo && (
                <div className="col-span-4">
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2 border-b border-slate-200 pb-1.5">Payment Information</h3>

                    <div className="space-y-1.5 text-sm">
                      {invoice.bank_name && (
                        <div>
                          <p className="text-xs text-slate-500">Bank Name</p>
                          <p className="font-medium text-slate-900">{invoice.bank_name}</p>
                        </div>
                      )}
                      {invoice.bank_account_number && (
                        <div>
                          <p className="text-xs text-slate-500">Account Number</p>
                          <p className="font-medium font-mono text-slate-900">{invoice.bank_account_number}</p>
                        </div>
                      )}
                      {invoice.bank_ifsc && (
                        <div>
                          <p className="text-xs text-slate-500">Routing / IFSC</p>
                          <p className="font-medium font-mono text-slate-900">{invoice.bank_ifsc}</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Right Column: Financials */}
              <div className={hasBankInfo ? 'col-span-3' : 'col-span-5'}>
                <div className="space-y-1.5 text-sm text-slate-600 border-b border-slate-200 pb-2 mb-2">

                  <div className="flex justify-between">
                    <span>Subtotal</span>
                    <span className="font-medium text-slate-900">{formatMoney(invoice.subtotal)}</span>
                  </div>

                  {parseFloat(invoice.discount_amount || 0) > 0 && (
                    <div className="flex justify-between">
                      <span>Discount</span>
                      <span className="font-medium text-slate-900">- {formatMoney(invoice.discount_amount)}</span>
                    </div>
                  )}

                  {invoice.taxes?.map((tax: any) => (
                    <div className="flex justify-between" key={tax.id}>
                      <span>{tax.tax_type} ({parseFloat(tax.percentage)}%)</span>
                      <span className="font-medium text-slate-900">{formatMoney(tax.amount)}</span>
                    </div>
                  ))}

                  <div className="flex justify-between pt-1.5 border-t border-slate-100">
                    <span className="font-medium text-slate-900">Gross</span>
                    <span className="font-medium text-slate-900">{formatMoney(invoice.gross_amount)}</span>
                  </div>

                  {invoice.tds && (
                    <div className="flex justify-between text-rose-600">
                      <span>TDS ({parseFloat(invoice.tds.tds_percentage)}%)</span>
                      <span className="font-medium">- {formatMoney(invoice.tds.tds_amount)}</span>
                    </div>
                  )}

                </div>

                <div className="bg-slate-900 text-white rounded-lg p-3 text-center shadow-md">
                  <span className="block text-xs font-medium text-slate-400 uppercase tracking-widest mb-0.5">Total Payable</span>
                  <span className="block text-xl font-black tracking-tight">{formatMoney(invoice.total_payable)}</span>
                </div>

                {parseFloat(invoice.amount_paid || 0) > 0 && (
                  <div className="flex justify-between text-sm mt-2 px-1">
                    <span className="text-slate-500">Paid</span>
                    <span className="font-medium text-emerald-600">{formatMoney(invoice.amount_paid)}</span>
                  </div>
                )}
                {invoice.payment_status !== 'PAID' && parseFloat(invoice.amount_paid || 0) > 0 && (
                  <div className="flex justify-between text-sm px-1">
                    <span className="text-slate-500">Balance Due</span>
                    <span className="font-semibold text-slate-900">{formatMoney(invoice.balance_due)}</span>
                  </div>
                )}
              </div>

            </div>

            {/* Payment History */}
            {invoice.payments && invoice.payments.length > 0 && (
              <div className="mb-6">
                <h4 className="font-bold text-slate-800 uppercase tracking-wider mb-2 text-xs">Payment History</h4>
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="text-[11px] text-slate-400 uppercase tracking-wide border-b border-slate-200">
                      <th className="py-2 font-medium">Voucher</th>
                      <th className="py-2 font-medium">Date</th>
                      <th className="py-2 font-medium">Method</th>
                      <th className="py-2 font-medium">Reference</th>
                      <th className="py-2 font-medium text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {invoice.payments
                      .filter((p: any) => p.status === 'SUCCESS')
                      .map((p: any) => (
                        <tr key={p.id}>
                          <td className="py-2 font-mono text-xs text-slate-600">{p.payment_reference || '—'}</td>
                          <td className="py-2 text-slate-700">{new Date(p.payment_date || p.received_at).toLocaleDateString()}</td>
                          <td className="py-2 text-slate-700 capitalize">{(p.payment_method || '—').toLowerCase().replace('_', ' ')}</td>
                          <td className="py-2 text-slate-500 font-mono text-xs">{p.transaction_reference || '—'}</td>
                          <td className="py-2 text-right font-medium text-slate-900">{formatMoney(p.amount)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Footer / Notes Block */}
            <div className="grid grid-cols-3 gap-6 pt-4 border-t border-slate-200">
              <div className="col-span-2 text-xs text-slate-500 leading-relaxed pr-6">
                <h4 className="font-bold text-slate-800 uppercase tracking-wider mb-1">Notes & Terms</h4>
                {invoice.invoice_terms ? (
                  <p className="whitespace-pre-line">{invoice.invoice_terms}</p>
                ) : (
                  <p>Payment is due within the stipulated timeframe. Late payments may incur interest charges. Please include the invoice number as the payment reference.</p>
                )}
              </div>

              <div className="col-span-1 text-center">
                <p className="text-sm font-medium text-slate-800 mb-3">Thank you for your business!</p>
                <div className="border-t border-slate-300 w-3/4 mx-auto pt-1.5">
                  <p className="text-xs font-bold text-slate-900 uppercase tracking-wide">Authorized Signatory</p>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

      {showPaymentModal && (
        <RecordPaymentModal
          projectId={projectId || invoice.id}
          invoice={invoice}
          onClose={() => setShowPaymentModal(false)}
          onRecorded={(message) => {
            reloadInvoice()
            setPaymentSuccess(message)
            setShowPaymentModal(false)
          }}
        />
      )}
    </div>
  )
}
