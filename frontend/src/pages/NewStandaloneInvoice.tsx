import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ClassificationPicker from '../components/ClassificationPicker'
import { listMasterClients, createStandaloneInvoice } from '../api/client'

interface LineItem {
  description: string
  amount: string
  hours: string
  classification: { id: string; hsn_sac_code: string; description: string } | null
}

const EMPTY_ITEM: LineItem = { description: '', amount: '', hours: '', classification: null }

export default function NewStandaloneInvoice() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<any[]>([])
  const [clientId, setClientId] = useState('')
  const [items, setItems] = useState<LineItem[]>([{ ...EMPTY_ITEM }])
  const [tdsApplicable, setTdsApplicable] = useState(false)
  const [poNumber, setPoNumber] = useState('')
  const [paymentTerms, setPaymentTerms] = useState('')
  const [discountAmount, setDiscountAmount] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listMasterClients()
      .then(setClients)
      .catch(() => {})
  }, [])

  function updateItem(index: number, patch: Partial<LineItem>) {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)))
  }

  function addItem() {
    setItems((prev) => [...prev, { ...EMPTY_ITEM }])
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  const subtotal = items.reduce((sum, it) => sum + (parseFloat(it.amount) || 0), 0)

  const isValid =
    clientId !== '' &&
    items.length > 0 &&
    items.every((it) => it.description.trim() !== '' && parseFloat(it.amount) > 0)

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const invoice = await createStandaloneInvoice({
        client_id: clientId,
        items: items.map((it) => ({
          source_type: 'CUSTOM',
          amount: parseFloat(it.amount),
          description: it.description.trim(),
          hours: it.hours ? parseFloat(it.hours) : null,
          billing_classification_id: it.classification?.id || null,
        })),
        tds_applicable: tdsApplicable,
        po_number: poNumber || null,
        payment_terms: paymentTerms || null,
        discount_amount: discountAmount ? parseFloat(discountAmount) : null,
      })
      navigate(`/invoice/standalone/${invoice.id}`)
    } catch (e: any) {
      setError(e.message || 'Failed to create invoice')
      setSubmitting(false)
    }
  }

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Topbar showBack title="New Standalone Invoice" subtitle="Bill a client directly — no project required." />
      <div className="p-8 space-y-6 max-w-4xl mx-auto">
        <Card title="Client">
          <select
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300"
          >
            <option value="">-- Choose a client --</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.company_name || c.contact_person}</option>
            ))}
          </select>
        </Card>

        <Card title="Line Items">
          <div className="space-y-6">
            {items.map((item, index) => (
              <div key={index} className="flex gap-4 items-start p-4 bg-slate-50 rounded-lg border border-slate-200">
                <div className="flex-1 space-y-4">
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
                      <input
                        type="text"
                        value={item.description}
                        onChange={(e) => updateItem(index, { description: e.target.value })}
                        className="w-full border-slate-200 rounded p-2 text-sm"
                        placeholder="Description to appear on invoice"
                      />
                    </div>
                    <div className="w-1/4">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Amount (₹)</label>
                      <input
                        type="number"
                        value={item.amount}
                        onChange={(e) => updateItem(index, { amount: e.target.value })}
                        className="w-full border-slate-200 rounded p-2 text-sm"
                        placeholder="0.00"
                      />
                    </div>
                    <div className="w-1/6">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Hours</label>
                      <input
                        type="number"
                        value={item.hours}
                        onChange={(e) => updateItem(index, { hours: e.target.value })}
                        className="w-full border-slate-200 rounded p-2 text-sm"
                        placeholder="optional"
                      />
                    </div>
                  </div>
                  <ClassificationPicker
                    description={item.description}
                    value={item.classification}
                    noSource
                    onChange={(choice) => updateItem(index, { classification: choice })}
                  />
                </div>
                <button
                  onClick={() => removeItem(index)}
                  disabled={items.length === 1}
                  className="text-slate-400 hover:text-red-500 disabled:opacity-30 p-2"
                >
                  ✕
                </button>
              </div>
            ))}

            <button
              onClick={addItem}
              className="text-sm font-medium text-brand-600 bg-brand-50 px-4 py-2 rounded-lg hover:bg-brand-100"
            >
              + Add Line Item
            </button>

            <div className="pt-4 border-t border-slate-100 grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">PO Number (optional)</label>
                <input
                  type="text"
                  value={poNumber}
                  onChange={(e) => setPoNumber(e.target.value)}
                  className="w-full border-slate-200 rounded p-2 text-sm"
                  placeholder="e.g. PO-2026-045"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Payment Terms (optional)</label>
                <input
                  type="text"
                  value={paymentTerms}
                  onChange={(e) => setPaymentTerms(e.target.value)}
                  className="w-full border-slate-200 rounded p-2 text-sm"
                  placeholder="e.g. Net 30"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Discount (₹, optional)</label>
                <input
                  type="number"
                  min="0"
                  value={discountAmount}
                  onChange={(e) => setDiscountAmount(e.target.value)}
                  className="w-full border-slate-200 rounded p-2 text-sm"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
                <input type="checkbox" checked={tdsApplicable} onChange={(e) => setTdsApplicable(e.target.checked)} />
                <span>Apply TDS Deduction</span>
              </label>
            </div>

            {error && <div className="text-sm text-coral-600 bg-coral-50 p-3 rounded-lg">{error}</div>}

            <div className="pt-4 flex items-center justify-between">
              <div className="text-sm text-slate-500">
                Subtotal <span className="font-semibold text-slate-800 ml-1">₹{subtotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
              </div>
              <button
                disabled={!isValid || submitting}
                onClick={submit}
                className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-medium text-sm px-6 py-2.5 rounded-full"
              >
                {submitting ? 'Generating...' : 'Generate Draft Invoice'}
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
