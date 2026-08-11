import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { inr } from '../components/EstimationResult'
import { createManualEstimation, listClients } from '../api/client'
import type { ClientGroup } from '../api/types'

interface LineItemRow {
  description: string
  quantity: number
  rate: number
}

const EMPTY_ROW: LineItemRow = { description: '', quantity: 1, rate: 0 }

export default function NewInvoice() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<ClientGroup[] | null>(null)

  useEffect(() => {
    listClients()
      .then((r) => setClients(r.clients))
      .catch(() => {})
  }, [])

  const uninvoiced = (clients ?? []).flatMap((c) => c.estimations.filter((e) => !e.has_invoice))

  return (
    <div className="flex-1">
      <Topbar title="New Invoice" subtitle="Create an invoice manually, or generate one from an existing estimation." />
      <div className="p-8 space-y-6">
        {uninvoiced.length > 0 && (
          <Card title="From an Existing Estimation">
            <ul className="divide-y divide-slate-100">
              {uninvoiced.slice(0, 6).map((e) => (
                <li key={e.base_name} className="flex items-center justify-between py-2.5">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-700 truncate">{e.project_name}</div>
                    <div className="text-xs text-slate-400">{e.client_name}</div>
                  </div>
                  <button
                    onClick={() => navigate(`/invoice/${e.base_name}`)}
                    className="text-sm font-medium bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-600 px-4 py-2 rounded-full shrink-0"
                  >
                    Generate Invoice
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <ManualInvoiceForm onCreated={(baseName) => navigate(`/invoice/${baseName}`)} />
      </div>
    </div>
  )
}

function ManualInvoiceForm({ onCreated }: { onCreated: (baseName: string) => void }) {
  const [clientName, setClientName] = useState('')
  const [projectName, setProjectName] = useState('')
  const [rows, setRows] = useState<LineItemRow[]>([{ ...EMPTY_ROW }])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const total = rows.reduce((sum, r) => sum + r.quantity * r.rate, 0)
  const canSubmit = clientName.trim() && projectName.trim() && rows.some((r) => r.description.trim() && r.quantity > 0)

  function updateRow(i: number, patch: Partial<LineItemRow>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }

  function addRow() {
    setRows((prev) => [...prev, { ...EMPTY_ROW }])
  }

  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i))
  }

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const { base_name } = await createManualEstimation({
        client_name: clientName.trim(),
        project_name: projectName.trim(),
        line_items: rows
          .filter((r) => r.description.trim() && r.quantity > 0)
          .map((r) => ({ description: r.description.trim(), quantity: r.quantity, rate: r.rate })),
      })
      onCreated(base_name)
    } catch (e: any) {
      setError(e.message || 'Failed to create invoice')
      setSubmitting(false)
    }
  }

  return (
    <Card title="Manual Invoice">
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div>
          <label className="text-sm font-medium text-slate-600">Client Name <span className="text-coral-500">*</span></label>
          <input
            value={clientName}
            onChange={(e) => setClientName(e.target.value)}
            placeholder="Acme Corp"
            className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
          />
        </div>
        <div>
          <label className="text-sm font-medium text-slate-600">Project / Description <span className="text-coral-500">*</span></label>
          <input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Website maintenance — July"
            className="mt-2 w-full border border-slate-200 rounded-2xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
          />
        </div>
      </div>

      <div className="mt-4">
        <label className="text-sm font-medium text-slate-600 block mb-3">Line Items <span className="text-coral-500">*</span></label>
        <div className="grid grid-cols-12 gap-2 items-center mb-2 px-1">
          <div className="col-span-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Item / Description <span className="text-coral-500">*</span></div>
          <div className="col-span-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Qty / Hours <span className="text-coral-500">*</span></div>
          <div className="col-span-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">Rate (₹)</div>
          <div className="col-span-2 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right pr-8">Amount</div>
        </div>
        <div className="space-y-2">
          {rows.map((row, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-center">
              <input
                value={row.description}
                onChange={(e) => updateRow(i, { description: e.target.value })}
                placeholder="e.g. Web Development"
                className="col-span-6 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              <input
                type="number"
                min={1}
                max={99999}
                value={row.quantity}
                onChange={(e) => updateRow(i, { quantity: Math.min(99999, Math.max(1, Number(e.target.value))) })}
                placeholder="1"
                className="col-span-2 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              <input
                type="number"
                min={0}
                max={9999999}
                value={row.rate}
                onChange={(e) => updateRow(i, { rate: Math.min(9999999, Math.max(0, Number(e.target.value))) })}
                placeholder="0"
                className="col-span-2 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              <div className="col-span-1 text-sm font-medium text-slate-700 tabular-nums text-right">{inr(row.quantity * row.rate)}</div>
            <button
              onClick={() => removeRow(i)}
              disabled={rows.length === 1}
              className="col-span-1 text-slate-300 hover:text-coral-500 disabled:opacity-30 text-lg"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <div className="flex justify-end mt-3">
        <button onClick={addRow} className="text-sm font-medium text-brand-600 hover:underline">
          + Add line item
        </button>
      </div>
      </div>

      <div className="flex items-center justify-between mt-5 pt-4 border-t border-slate-100">
        <div className="text-sm text-slate-500">
          Subtotal <span className="font-semibold text-slate-800 ml-1">{inr(total)}</span>
        </div>
        {error && <div className="text-sm text-coral-600">{error}</div>}
        <button
          disabled={!canSubmit || submitting}
          onClick={submit}
          className="bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-sm font-medium px-6 py-2.5 rounded-full"
        >
          {submitting ? 'Creating…' : 'Continue to Invoice →'}
        </button>
      </div>
    </Card>
  )
}
