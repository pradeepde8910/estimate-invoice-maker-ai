import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ClassificationPicker from '../components/ClassificationPicker'
import { listMasterClients, createMasterClient, createStandaloneInvoice } from '../api/client'
import { EMAIL_RE, PHONE_RE, GSTIN_RE, formatGSTIN, formatPhone, uiFormatPhone } from '../utils/validation'

interface LineItem {
  description: string
  amount: string
  hours: string
  classification: { id: string; hsn_sac_code: string; description: string } | null
}

const EMPTY_ITEM: LineItem = { description: '', amount: '', hours: '', classification: null }

const EMPTY_NEW_CLIENT = {
  company_name: '',
  contact_person: '',
  email: '',
  phone: '',
  gstin: '',
  billing_address: '',
}

export default function NewStandaloneInvoice() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<any[]>([])
  const [clientMode, setClientMode] = useState<'existing' | 'new'>('existing')
  const [clientId, setClientId] = useState('')
  const [newClient, setNewClient] = useState({ ...EMPTY_NEW_CLIENT })
  const [clientFieldErrors, setClientFieldErrors] = useState<Record<string, string>>({})
  const [items, setItems] = useState<LineItem[]>([{ ...EMPTY_ITEM }])
  const [tdsApplicable, setTdsApplicable] = useState(false)
  const [poNumber, setPoNumber] = useState('')
  const [paymentTerms, setPaymentTerms] = useState('')
  const [discountAmount, setDiscountAmount] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savingClient, setSavingClient] = useState(false)
  const [clientSaved, setClientSaved] = useState<string | null>(null)

  useEffect(() => {
    listMasterClients()
      .then(setClients)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!clientSaved) return
    const t = setTimeout(() => setClientSaved(null), 4000)
    return () => clearTimeout(t)
  }, [clientSaved])

  // Same rules as ClientDetailsEditor (frontend/src/components/ClientDetailsEditor.tsx)
  // so a client entered here and one edited from an estimation are held to
  // the same standard. Returns the field-error map; empty means valid.
  function validateNewClient(): Record<string, string> {
    const errors: Record<string, string> = {}
    if (!newClient.company_name.trim() && !newClient.contact_person.trim()) {
      errors.general = 'At least Company Name or Contact Person is required.'
    }
    if (newClient.email && !EMAIL_RE.test(newClient.email)) {
      errors.email = 'Enter a valid email address'
    }
    if (newClient.phone && !PHONE_RE.test(formatPhone(newClient.phone))) {
      errors.phone = 'Enter a valid 10-digit Indian mobile number'
    }
    if (newClient.gstin && !GSTIN_RE.test(newClient.gstin.toUpperCase())) {
      errors.gstin = 'Enter a valid GSTIN, e.g. 22AAAAA0000A1Z5'
    }
    return errors
  }

  const newClientValid = clientMode === 'new' ? Object.keys(validateNewClient()).length === 0 : true

  // Saves the new-client form as its own client record right away, rather
  // than only implicitly on invoice submit — so it's usable even before line
  // items are filled in, and so it's reusable on future invoices immediately.
  async function saveNewClient() {
    const errors = validateNewClient()
    setClientFieldErrors(errors)
    if (Object.keys(errors).length > 0) {
      setError(errors.general || 'Please fix the highlighted client fields.')
      return
    }
    setSavingClient(true)
    setError(null)
    try {
      const created = await createMasterClient({
        company_name: newClient.company_name || null,
        contact_person: newClient.contact_person || null,
        email: newClient.email || null,
        phone: newClient.phone || null,
        gstin: newClient.gstin || null,
        billing_address: newClient.billing_address || null,
      })
      setClients((prev) => [...prev, created])
      setClientId(created.id)
      setClientMode('existing')
      setNewClient({ ...EMPTY_NEW_CLIENT })
      setClientSaved(created.company_name || created.contact_person || 'Client')
    } catch (e: any) {
      setError(e.message || 'Failed to save client')
    } finally {
      setSavingClient(false)
    }
  }

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
    (clientMode === 'existing' ? clientId !== '' : newClientValid) &&
    items.length > 0 &&
    items.every((it) => it.description.trim() !== '' && parseFloat(it.amount) > 0)

  async function submit() {
    setSubmitting(true)
    setError(null)

    let resolvedClientId = clientId
    if (clientMode === 'new') {
      const errors = validateNewClient()
      setClientFieldErrors(errors)
      if (Object.keys(errors).length > 0) {
        setError(errors.general || 'Please fix the highlighted client fields.')
        setSubmitting(false)
        return
      }
      try {
        const created = await createMasterClient({
          company_name: newClient.company_name || null,
          contact_person: newClient.contact_person || null,
          email: newClient.email || null,
          phone: newClient.phone || null,
          gstin: newClient.gstin || null,
          billing_address: newClient.billing_address || null,
        })
        resolvedClientId = created.id
      } catch (e: any) {
        setError(e.message || 'Failed to create client')
        setSubmitting(false)
        return
      }
    }

    try {
      const invoice = await createStandaloneInvoice({
        client_id: resolvedClientId,
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
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar showBack title="New Standalone Invoice" subtitle="Bill a client directly — no project required." />
      <div className="p-8 space-y-6 max-w-4xl mx-auto">
        <Card title="Client">
          <div className="flex gap-2 mb-4">
            <button
              type="button"
              onClick={() => setClientMode('existing')}
              className={`text-sm font-medium px-4 py-2 rounded-full ${
                clientMode === 'existing' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              Existing Client
            </button>
            <button
              type="button"
              onClick={() => setClientMode('new')}
              className={`text-sm font-medium px-4 py-2 rounded-full ${
                clientMode === 'new' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              + New Client
            </button>
          </div>

          {clientSaved && (
            <div className="mb-4 text-sm text-emerald-700 bg-emerald-50 rounded-lg px-4 py-2">
              "{clientSaved}" saved — you can pick it from Existing Client on this or future invoices.
            </div>
          )}

          {clientMode === 'existing' ? (
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
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Company / Organization Name</label>
                <input
                  type="text"
                  value={newClient.company_name}
                  onChange={(e) => {
                    setNewClient({ ...newClient, company_name: e.target.value })
                    setClientFieldErrors({ ...clientFieldErrors, company_name: '' })
                  }}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                  placeholder="e.g. Acme Corp"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Contact Person</label>
                <input
                  type="text"
                  value={newClient.contact_person}
                  onChange={(e) => {
                    setNewClient({ ...newClient, contact_person: e.target.value })
                    setClientFieldErrors({ ...clientFieldErrors, contact_person: '' })
                  }}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                  placeholder="e.g. Jane Doe"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Email</label>
                <input
                  type="email"
                  value={newClient.email}
                  onChange={(e) => {
                    setNewClient({ ...newClient, email: e.target.value })
                    setClientFieldErrors({ ...clientFieldErrors, email: '' })
                  }}
                  className={`w-full border rounded-xl px-3 py-2 text-sm ${clientFieldErrors.email ? 'border-coral-300' : 'border-slate-200'}`}
                />
                {clientFieldErrors.email && <p className="text-xs text-coral-600 mt-1">{clientFieldErrors.email}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Phone</label>
                <input
                  type="tel"
                  inputMode="numeric"
                  value={newClient.phone ? uiFormatPhone(newClient.phone) : ''}
                  onChange={(e) => {
                    setNewClient({ ...newClient, phone: uiFormatPhone(e.target.value) })
                    setClientFieldErrors({ ...clientFieldErrors, phone: '' })
                  }}
                  className={`w-full border rounded-xl px-3 py-2 text-sm ${clientFieldErrors.phone ? 'border-coral-300' : 'border-slate-200'}`}
                />
                {clientFieldErrors.phone && <p className="text-xs text-coral-600 mt-1">{clientFieldErrors.phone}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">GSTIN / Tax ID</label>
                <input
                  type="text"
                  value={newClient.gstin}
                  onChange={(e) => {
                    setNewClient({ ...newClient, gstin: formatGSTIN(e.target.value) })
                    setClientFieldErrors({ ...clientFieldErrors, gstin: '' })
                  }}
                  className={`w-full border rounded-xl px-3 py-2 text-sm ${clientFieldErrors.gstin ? 'border-coral-300' : 'border-slate-200'}`}
                />
                {clientFieldErrors.gstin && <p className="text-xs text-coral-600 mt-1">{clientFieldErrors.gstin}</p>}
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-medium text-slate-500 mb-1">Billing Address</label>
                <textarea
                  value={newClient.billing_address}
                  onChange={(e) => setNewClient({ ...newClient, billing_address: e.target.value })}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm h-20"
                />
              </div>
              {clientFieldErrors.general && (
                <div className="md:col-span-2 text-xs text-coral-600">{clientFieldErrors.general}</div>
              )}

              {error && (
                <div className="md:col-span-2 text-sm text-coral-600 bg-coral-50 p-3 rounded-lg">{error}</div>
              )}

              <div className="md:col-span-2 flex justify-end pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={saveNewClient}
                  disabled={savingClient}
                  className="text-sm font-medium bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white px-5 py-2 rounded-full"
                >
                  {savingClient ? 'Saving…' : 'Save Client'}
                </button>
              </div>
            </div>
          )}
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
