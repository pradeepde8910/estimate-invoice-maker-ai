import { useState } from 'react'
import { createPortal } from 'react-dom'
import { recordManualPayment } from '../api/client'

const PAYMENT_METHODS = [
  { value: 'BANK_TRANSFER', label: 'Bank Transfer' },
  { value: 'UPI', label: 'UPI' },
  { value: 'CHEQUE', label: 'Cheque' },
  { value: 'CASH', label: 'Cash' },
  { value: 'CARD', label: 'Card' },
  { value: 'OTHER', label: 'Other' },
]

function money(v: number) {
  return `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
}

function todayDateInputValue(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function RecordPaymentModal({
  projectId,
  invoice,
  onClose,
  onRecorded,
}: {
  projectId: string
  invoice: any
  onClose: () => void
  onRecorded: (message: string) => void
}) {
  const totalPayable = parseFloat(invoice.total_payable)
  const alreadyPaid = parseFloat(invoice.amount_paid ?? 0)
  const balanceDue = invoice.balance_due != null ? parseFloat(invoice.balance_due) : totalPayable - alreadyPaid

  const [amount, setAmount] = useState(balanceDue.toFixed(2))
  const [method, setMethod] = useState('')
  const [date, setDate] = useState(todayDateInputValue())
  const [reference, setReference] = useState('')
  const [remarks, setRemarks] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const amountValue = parseFloat(amount)
  const amountValid = !isNaN(amountValue) && amountValue > 0 && amountValue <= balanceDue + 0.005
  const remainingAfter = balanceDue - (isNaN(amountValue) ? 0 : amountValue)
  const willBeFullyPaid = amountValid && remainingAfter <= 0.005

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!amountValid || !method) return
    setBusy(true)
    setError(null)
    try {
      const payment = await recordManualPayment(projectId, invoice.id, {
        amount: amountValue,
        payment_method: method,
        payment_date: new Date(date).toISOString(),
        transaction_reference: reference || undefined,
        remarks: remarks || undefined,
      })
      onRecorded(
        `${money(amountValue)} recorded against ${invoice.invoice_number || 'this invoice'} ` +
        `(${payment.payment_reference || 'voucher'}).`
      )
    } catch (err: any) {
      setError(err.message || 'Failed to record payment')
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={busy ? undefined : onClose} />
      <div className="relative bg-white rounded-3xl shadow-card w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          disabled={busy}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors disabled:opacity-40 disabled:pointer-events-none"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>

        <h3 className="text-xl font-semibold tracking-tight text-slate-800 mb-1 pr-6">Record Payment</h3>
        <p className="text-sm text-slate-500 mb-4">{invoice.invoice_number || 'Draft invoice'}</p>

        <div className="grid grid-cols-3 gap-3 mb-5 text-sm">
          <div className="bg-slate-50 rounded-2xl p-3">
            <div className="text-[10px] text-slate-400 uppercase tracking-wide mb-0.5">Invoice Total</div>
            <div className="font-semibold text-slate-800">{money(totalPayable)}</div>
          </div>
          <div className="bg-slate-50 rounded-2xl p-3">
            <div className="text-[10px] text-slate-400 uppercase tracking-wide mb-0.5">Already Paid</div>
            <div className="font-semibold text-slate-800">{money(alreadyPaid)}</div>
          </div>
          <div className="bg-brand-50 rounded-2xl p-3">
            <div className="text-[10px] text-brand-600 uppercase tracking-wide mb-0.5">Balance Due</div>
            <div className="font-semibold text-brand-700">{money(balanceDue)}</div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Payment Amount</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max={balanceDue}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={busy}
              className={`w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${
                amount && !amountValid ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'
              }`}
            />
            {amount && !amountValid && (
              <p className="text-xs text-coral-600 mt-1">
                Enter an amount between ₹0.01 and the balance due ({money(balanceDue)}).
              </p>
            )}
            {amountValid && (
              <p className="text-xs text-slate-400 mt-1">
                Remaining after this payment: <span className="font-medium text-slate-600">{money(Math.max(remainingAfter, 0))}</span>
                {willBeFullyPaid && <span className="text-brand-600 font-medium"> — invoice will be fully paid</span>}
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Payment Method</label>
            <select
              required
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              disabled={busy}
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              <option value="" disabled>Select a payment method…</option>
              {PAYMENT_METHODS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Payment Date</label>
              <input
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={busy}
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Transaction Reference</label>
              <input
                type="text"
                placeholder="e.g. TXN-20260822-001"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                disabled={busy}
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Notes (optional)</label>
            <input
              type="text"
              placeholder="e.g. First installment"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              disabled={busy}
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
          </div>

          {error && <div className="p-3 bg-coral-50 text-coral-600 text-sm rounded-xl">{error}</div>}

          <div className="flex gap-3 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="px-5 py-2.5 rounded-full text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !amountValid || !method}
              className="px-5 py-2.5 rounded-full text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 shadow-sm transition-colors disabled:opacity-50"
            >
              {busy ? 'Recording…' : 'Record Payment'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}
