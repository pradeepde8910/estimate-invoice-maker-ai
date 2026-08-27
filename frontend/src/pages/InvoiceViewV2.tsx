import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import RecordPaymentModal from '../components/RecordPaymentModal'
import { getInvoiceDetails, downloadInvoicePdf, getOrganization } from '../api/client'
import type { OrganizationProfile } from '../api/types'

const ONES = [
  '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
  'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
  'Seventeen', 'Eighteen', 'Nineteen',
]
const TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

function under1000Words(n: number): string {
  if (n === 0) return ''
  if (n < 20) return ONES[n]
  if (n < 100) return (TENS[Math.floor(n / 10)] + (n % 10 ? ` ${ONES[n % 10]}` : '')).trim()
  return (ONES[Math.floor(n / 100)] + ' Hundred' + (n % 100 ? ` ${under1000Words(n % 100)}` : '')).trim()
}

// Indian numbering (crore/lakh/thousand) amount-in-words — mirrors
// amount_in_words() in backend/app/services/pdf_service.py so the web view
// and the downloaded PDF read the same.
function amountInWords(amount: number): string {
  let rupees = Math.trunc(amount)
  const paise = Math.round((amount - rupees) * 100)

  let rupeeWords = 'Zero'
  if (rupees > 0) {
    const parts: string[] = []
    const crore = Math.floor(rupees / 10_000_000); rupees %= 10_000_000
    const lakh = Math.floor(rupees / 100_000); rupees %= 100_000
    const thousand = Math.floor(rupees / 1000); rupees %= 1000
    const hundred = rupees

    if (crore) parts.push(`${under1000Words(crore)} Crore`)
    if (lakh) parts.push(`${under1000Words(lakh)} Lakh`)
    if (thousand) parts.push(`${under1000Words(thousand)} Thousand`)
    if (hundred) parts.push(under1000Words(hundred))
    rupeeWords = parts.join(' ')
  }

  let words = `Rupees ${rupeeWords} Only`
  if (paise) words = `Rupees ${rupeeWords} and ${under1000Words(paise)} Paise Only`
  return words
}

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

  const formatMoney = (val: string | number) => `₹${parseFloat(val.toString()).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`

  // Group + number line items by milestone/component, then by requirement,
  // then flatten to a list of "chunks" — one per requirement subgroup (or
  // one per group, for a group with no requirement breakdown). A chunk is
  // the smallest unit pagination below is allowed to break between: a
  // milestone with many requirements can legitimately span several pages
  // (that's the whole point of real pagination), but a requirement's own
  // rows always stay together.
  //
  // Computed with optional chaining (rather than after the loading/error
  // guards below) because the pagination hooks that consume it must be
  // called unconditionally on every render — React's rules of hooks don't
  // allow skipping useMemo/useLayoutEffect calls while `invoice` is still
  // loading.
  const chunks = useMemo(() => {
    let runningSno = 0
    const grouped: Record<string, any> = {}
    const groupOrder: string[] = []
    ;(invoice?.items ?? []).forEach((item: any) => {
      const groupId = item.milestone_id || (item.component_id ? `comp_${item.component_id}` : 'other')
      const groupName = item.milestone_name || (item.component_id ? 'Commercial Components' : 'Other Items')
      if (!grouped[groupId]) {
        grouped[groupId] = { id: groupId, name: groupName, requirements: {}, reqOrder: [], total: 0, itemCount: 0 }
        groupOrder.push(groupId)
      }
      const reqName = item.requirement_name || 'General'
      if (!grouped[groupId].requirements[reqName]) {
        grouped[groupId].requirements[reqName] = { name: reqName, items: [], total: 0 }
        grouped[groupId].reqOrder.push(reqName)
      }
      grouped[groupId].requirements[reqName].items.push(item)
      grouped[groupId].requirements[reqName].total += parseFloat(item.amount)
      grouped[groupId].total += parseFloat(item.amount)
      grouped[groupId].itemCount += 1
    })

    const flat: any[] = []
    groupOrder.forEach((groupId) => {
      const g = grouped[groupId]
      g.reqOrder.forEach((reqName: string, reqIdx: number) => {
        const req = g.requirements[reqName]
        flat.push({
          key: `${groupId}::${reqName}`,
          groupId,
          groupName: g.name,
          groupTotal: g.total,
          groupItemCount: g.itemCount,
          isFirstChunkOfGroup: reqIdx === 0,
          isLastChunkOfGroup: reqIdx === g.reqOrder.length - 1,
          reqName,
          items: req.items.map((it: any) => ({ ...it, __sno: ++runningSno })),
        })
      })
    })
    return flat
  }, [invoice])

  const hasBankInfo = Boolean(invoice?.bank_name || invoice?.bank_account_number || invoice?.bank_ifsc)
  const isStandalone = invoice ? (invoice.invoice_type === 'STANDALONE' || !invoice.project_id) : false

  // ── Pagination ──────────────────────────────────────────────────────────
  // A4 is a strict physical size, so an invoice with enough line items must
  // split across several A4 sheets rather than one ever-taller box. We do
  // this by rendering everything once, hidden, to measure real DOM heights
  // (fonts/wrapping make heights impossible to predict analytically), then
  // greedily packing chunks into pages against that A4 budget. Each chunk is
  // measured as if it opens its own group header (a conservative
  // over-estimate when it actually continues a group already open on the
  // same page — safe, since it only makes pagination a little more
  // cautious, never causes overflow).
  const pageBudgetRef = useRef<HTMLDivElement | null>(null)
  const fullHeaderRef = useRef<HTMLDivElement | null>(null)
  const miniHeaderRef = useRef<HTMLDivElement | null>(null)
  const theadRef = useRef<HTMLTableSectionElement | null>(null)
  const trailingRef = useRef<HTMLDivElement | null>(null)
  const chunkRefs = useRef<(HTMLDivElement | null)[]>([])

  const [measurements, setMeasurements] = useState<{
    pageContentPx: number
    fullHeaderPx: number
    miniHeaderPx: number
    theadPx: number
    trailingPx: number
    chunkPx: number[]
  } | null>(null)

  useLayoutEffect(() => {
    if (!invoice) return
    const chunkPx = chunks.map((_: any, idx: number) => chunkRefs.current[idx]?.offsetHeight || 0)
    setMeasurements({
      pageContentPx: pageBudgetRef.current?.offsetHeight || 0,
      fullHeaderPx: fullHeaderRef.current?.offsetHeight || 0,
      miniHeaderPx: miniHeaderRef.current?.offsetHeight || 0,
      theadPx: theadRef.current?.offsetHeight || 0,
      trailingPx: trailingRef.current?.offsetHeight || 0,
      chunkPx,
    })
    // Re-measure whenever the data that could change any of these heights
    // changes; `chunks` itself is a fresh array every render so it isn't a
    // safe dependency, hence `chunks.length` as a stable proxy.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoice, org, chunks.length])

  const pagination = useMemo(() => {
    if (!measurements || chunks.length === 0) return null
    const { pageContentPx, fullHeaderPx, miniHeaderPx, theadPx, trailingPx, chunkPx } = measurements
    const page1Budget = pageContentPx - fullHeaderPx - theadPx
    const contBudget = pageContentPx - miniHeaderPx - theadPx

    const chunkPages: number[][] = []
    let current: number[] = []
    let budget = page1Budget
    chunks.forEach((_: any, idx: number) => {
      const h = chunkPx[idx] || 0
      if (current.length > 0 && h > budget) {
        chunkPages.push(current)
        current = []
        budget = contBudget
      }
      current.push(idx)
      budget -= h
    })
    chunkPages.push(current)

    const lastPageBudget = chunkPages.length === 1 ? page1Budget : contBudget
    const lastPageUsed = chunkPages[chunkPages.length - 1].reduce((s, idx) => s + (chunkPx[idx] || 0), 0)
    const trailingOnOwnPage = lastPageUsed + trailingPx > lastPageBudget

    return { chunkPages, trailingOnOwnPage }
  }, [measurements, chunks])

  if (loading) return <div className="p-8 text-center text-slate-500">Loading invoice...</div>
  if (error || !invoice) return <div className="p-8 text-center text-red-500">{error || 'Failed to load invoice.'}</div>

  // ---- `invoice` is guaranteed non-null from here on. ----

  // `forceGroupHeader`: render this chunk's group header even if it isn't
  // the group's true first chunk (it's continuing on a new page after a
  // break, so the group heading needs to repeat with a "(cont'd)" marker).
  // `suppressGroupHeader`: this chunk continues the same group as the one
  // rendered just before it on the same page, so skip the header entirely.
  function renderChunk(chunk: any, opts: { forceGroupHeader?: boolean; suppressGroupHeader?: boolean } = {}) {
    const showHeader = !opts.suppressGroupHeader
    const continued = Boolean(opts.forceGroupHeader) && !chunk.isFirstChunkOfGroup
    return (
      <React.Fragment key={chunk.key}>
        {showHeader && (
          <tr className="bg-slate-50">
            <td colSpan={5} className="py-1.5 px-3 text-xs font-bold text-slate-800 tracking-widest uppercase border-y border-slate-200">
              {chunk.groupName}{continued ? ' (cont’d)' : ''}
            </td>
          </tr>
        )}

        {chunk.reqName !== 'General' && (
          <tr className="bg-white">
            <td colSpan={5} className="py-1 px-5 text-[11px] font-bold text-slate-500 tracking-wide">
              {chunk.reqName}
            </td>
          </tr>
        )}

        {chunk.items.map((item: any) => (
          <tr key={item.id} className="hover:bg-slate-50/50">
            <td className="py-1.5 px-3 text-sm text-slate-500 font-mono">
              {item.__sno}
            </td>
            <td className={`py-1.5 ${chunk.reqName !== 'General' ? 'px-6' : 'px-3'} text-sm text-slate-800`}>
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
        ))}

        {chunk.isLastChunkOfGroup && chunk.groupItemCount > 1 && (
          <tr>
            <td colSpan={4} className="py-1.5 px-3 text-xs font-bold text-slate-500 text-right uppercase tracking-wider">Group Subtotal</td>
            <td className="py-1.5 px-3 text-sm font-bold text-slate-900 text-right bg-slate-50/50">
              {formatMoney(chunk.groupTotal)}
            </td>
          </tr>
        )}
      </React.Fragment>
    )
  }

  // Renders one page's chunk list, showing each chunk's group header only
  // once per group per page (skipping it for a chunk that continues the
  // same group as its predecessor on this same page).
  function renderChunksForPage(chunkIdxs: number[]) {
    let lastGroupId: string | null = null
    return chunkIdxs.map((idx) => {
      const chunk = chunks[idx]
      const sameGroupAsPrevious = chunk.groupId === lastGroupId
      lastGroupId = chunk.groupId
      return renderChunk(chunk, {
        forceGroupHeader: !sameGroupAsPrevious,
        suppressGroupHeader: sameGroupAsPrevious,
      })
    })
  }

  function tableHead(ref?: React.Ref<HTMLTableSectionElement>) {
    return (
      <thead ref={ref}>
        <tr className="bg-slate-900 text-white">
          <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider w-10">#</th>
          <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider">Description</th>
          <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider w-24">HSN/SAC</th>
          <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-right w-20">Hours</th>
          <th className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-right w-32">Taxable Amount</th>
        </tr>
      </thead>
    )
  }

  function miniHeader(pageNum: number, totalPages: number) {
    return (
      <div className="flex justify-between items-center mb-4 pb-2 border-b border-slate-200 text-xs text-slate-500">
        <div>
          <span className="font-bold text-slate-800">{org?.name || 'Invoice'}</span>
          <span className="mx-2">·</span>
          <span>{invoice.invoice_number || 'DRAFT'}</span>
        </div>
        <div>Page {pageNum} of {totalPages}</div>
      </div>
    )
  }

  const sellerBlock = (
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
  )

  const headerBlock = (
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
  )

  const billToBlock = (
    <div className="mb-6">
      <div className="bg-amber-50/50 border border-amber-100 rounded-lg p-4 max-w-md">
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
  )

  const trailingContent = (
    <>
      {/* Bottom Section Grid (Payment Info, Financials) */}
      <div className="grid grid-cols-12 gap-4 mb-4 items-start">

        {/* Left Column: Payment Info (omitted entirely when no bank details are configured) */}
        {hasBankInfo ? (
          <div className="col-span-7">
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
        ) : (
          <div className="col-span-7" />
        )}

        {/* Right Column: Financials */}
        <div className="col-span-5">
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
              <span className="font-medium text-slate-900">Total</span>
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

      {/* Amount in Words */}
      <div className="mb-6">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-widest mr-1.5">Amount in Words:</span>
        <span className="text-sm text-slate-700 italic">{amountInWords(parseFloat(invoice.total_payable))}</span>
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
    </>
  )

  const footerContent = (
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
        <p className="text-sm font-medium text-slate-800 mb-1">Thank you for your business!</p>
        {org?.name && <p className="text-xs text-slate-500 mb-6">For {org.name}</p>}
        <div className="border-t border-slate-300 w-3/4 mx-auto pt-1.5">
          <p className="text-xs font-bold text-slate-900 uppercase tracking-wide">Authorized Signatory</p>
        </div>
      </div>
    </div>
  )

  const totalPages = pagination ? pagination.chunkPages.length + (pagination.trailingOnOwnPage ? 1 : 0) : 1
  // Fallback (measurement not settled yet): everything on one page, so
  // there's no flash of empty content while heights are still being measured.
  const chunkPagesForRender: number[][] = pagination
    ? pagination.chunkPages
    : (chunks.length > 0 ? [chunks.map((_: any, i: number) => i)] : [[]])

  return (
    <div className="flex-1 bg-transparent min-h-screen pb-12">
      <Topbar showBack title={`Invoice ${invoice.invoice_number || 'Draft'}`} subtitle={invoice.project_name || invoice.client_name} />

      <div className="max-w-4xl mx-auto mt-8 px-4 print:max-w-none print:mt-0 print:px-0">

        {/* Actions Bar */}
        <div className="print:hidden flex justify-between items-center mb-4">
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
          <div className="print:hidden mb-4 text-sm text-brand-700 bg-brand-50 rounded-lg px-4 py-2">{paymentSuccess}</div>
        )}

        {downloadError && (
          <div className="print:hidden mb-4 text-sm text-coral-600 bg-coral-50 rounded-lg px-4 py-2">{downloadError}</div>
        )}

        {/* Hidden measurement scaffold — an off-screen dry run used only to
            read real DOM heights for pagination below; never shown to the
            user, and stripped from print output entirely (see index.css). */}
        <div
          className="print:hidden"
          style={{ position: 'fixed', top: 0, left: '-99999px', visibility: 'hidden', pointerEvents: 'none' }}
          aria-hidden="true"
        >
          <div ref={pageBudgetRef} style={{ height: '267mm' }} />
          <div style={{ width: '180mm' }}>
            <div ref={fullHeaderRef}>
              {sellerBlock}
              {headerBlock}
              {billToBlock}
            </div>
            <div ref={miniHeaderRef}>{miniHeader(1, 1)}</div>
            <table className="w-full text-left border-collapse">
              {tableHead(theadRef)}
              <tbody />
            </table>
            {chunks.map((chunk: any, idx: number) => (
              <div key={chunk.key} ref={(el) => { chunkRefs.current[idx] = el }}>
                <table className="w-full text-left border-collapse"><tbody>{renderChunk(chunk, { forceGroupHeader: true })}</tbody></table>
              </div>
            ))}
            <div ref={trailingRef}>
              {trailingContent}
              {footerContent}
            </div>
          </div>
        </div>

        {/* Invoice Paper — one or more strict A4 (210mm × 297mm) sheets */}
        {chunkPagesForRender.map((chunkIdxs: number[], pageIdx: number) => {
          const isLastGroupPage = pageIdx === chunkPagesForRender.length - 1
          const showTrailingHere = isLastGroupPage && !(pagination?.trailingOnOwnPage)
          return (
            <div key={pageIdx} className="invoice-a4-page mx-auto bg-white shadow-xl border border-slate-200 box-border mb-8 print:mb-0">
              <div className="p-[15mm] flex flex-col min-h-[267mm]">
                {pageIdx === 0 ? (
                  <>
                    {sellerBlock}
                    {headerBlock}
                    {billToBlock}
                  </>
                ) : (
                  miniHeader(pageIdx + 1, totalPages)
                )}

                <div className="mb-6">
                  <table className="w-full text-left border-collapse">
                    {tableHead()}
                    <tbody className="divide-y divide-slate-100 border-b border-slate-200">
                      {renderChunksForPage(chunkIdxs)}
                    </tbody>
                  </table>
                </div>

                {showTrailingHere ? (
                  <>
                    {trailingContent}
                    <div className="mt-auto">{footerContent}</div>
                  </>
                ) : (
                  <div className="mt-auto text-center text-[10px] text-slate-400 pt-4 border-t border-slate-100">
                    Continued on next page…
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {pagination?.trailingOnOwnPage && (
          <div className="invoice-a4-page mx-auto bg-white shadow-xl border border-slate-200 box-border mb-8 print:mb-0">
            <div className="p-[15mm] flex flex-col min-h-[267mm]">
              {miniHeader(totalPages, totalPages)}
              {trailingContent}
              <div className="mt-auto">{footerContent}</div>
            </div>
          </div>
        )}
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
