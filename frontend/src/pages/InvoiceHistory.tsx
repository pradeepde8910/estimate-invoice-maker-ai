import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { inr } from '../components/EstimationResult'
import { listClients } from '../api/client'
import type { ClientGroup } from '../api/types'

export default function InvoiceHistory() {
  const [clients, setClients] = useState<ClientGroup[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    listClients()
      .then((r) => setClients(r.clients))
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="flex-1">
      <Topbar title="Invoice History" subtitle="Every estimation, ready to be invoiced or already invoiced." />
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
        {!clients ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : clients.length === 0 ? (
          <Card className="text-center py-16">
            <div className="text-4xl mb-3">🧾</div>
            <p className="text-slate-500">No estimations yet. Run an Estimation first, or create a manual invoice above.</p>
            <button
              onClick={() => navigate('/estimation/new')}
              className="mt-5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium px-5 py-2.5 rounded-full"
            >
              Go to Estimation
            </button>
          </Card>
        ) : (
          <div className="space-y-5">
            {clients.map((c) => (
              <Card key={c.client_name}>
                <h3 className="font-semibold text-slate-800 mb-2">{c.client_name}</h3>
                <ul className="divide-y divide-slate-100">
                  {c.estimations.map((e) => (
                    <li key={e.base_name} className="flex items-center justify-between py-3">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-slate-700 truncate">{e.project_name}</div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {e.grand_total != null ? inr(e.grand_total) : '—'}
                          {e.invoice_meta && ` · ${e.invoice_meta.invoice_number}`}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {e.has_invoice && (
                          <span className="text-[11px] font-medium bg-brand-50 text-brand-600 px-2.5 py-1 rounded-full">
                            {e.invoice_meta?.status ?? 'Invoiced'}
                          </span>
                        )}
                        <button
                          onClick={() => navigate(`/invoice/${e.base_name}`)}
                          className="text-sm font-medium bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-600 px-4 py-2 rounded-full"
                        >
                          {e.has_invoice ? 'View Invoice' : 'Generate Invoice'}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
