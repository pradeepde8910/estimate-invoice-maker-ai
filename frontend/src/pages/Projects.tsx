import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { listProjects, downloadProjectStatement, listStandaloneInvoices } from '../api/client'

const money = (v: string | number) => '₹' + parseFloat(String(v)).toLocaleString('en-IN', { minimumFractionDigits: 2 })

// Mirrors ProjectReport's default column set in backend/app/services/reports/project_report.py —
// keep in sync if that list changes.
const EXPORT_COLUMNS = [
  'Project Number', 'Project Name', 'Client Name', 'Billing Type', 'Status', 'Contract Value', 'Created At',
]

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === 'Active'
      ? 'bg-emerald-50 text-emerald-700'
      : status === 'Completed'
      ? 'bg-slate-100 text-slate-600'
      : 'bg-blue-50 text-blue-700'
  return <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${tone}`}>{status}</span>
}

export default function Projects() {
  const [projects, setProjects] = useState<any[]>([])
  const [standaloneInvoices, setStandaloneInvoices] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [clientFilter, setClientFilter] = useState('')
  const [billingFilter, setBillingFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const [showDownloadPanel, setShowDownloadPanel] = useState(false)
  const [selectedColumns, setSelectedColumns] = useState<string[]>(EXPORT_COLUMNS)
  const [exportFormat, setExportFormat] = useState<'pdf' | 'excel' | 'csv'>('pdf')
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
    listStandaloneInvoices()
      .then(setStandaloneInvoices)
      .catch(() => {})
  }, [])

  const distinctClients = useMemo(
    () => Array.from(new Set(projects.map((p) => p.client_name).filter(Boolean))).sort(),
    [projects]
  )
  const distinctBillingTypes = useMemo(
    () => Array.from(new Set(projects.map((p) => p.billing_type).filter(Boolean))).sort(),
    [projects]
  )
  const distinctStatuses = useMemo(
    () => Array.from(new Set(projects.map((p) => p.status).filter(Boolean))).sort(),
    [projects]
  )

  const visible = projects.filter((p) => {
    const q = search.trim().toLowerCase()
    if (q) {
      const matches =
        p.project_name.toLowerCase().includes(q) ||
        p.project_number.toLowerCase().includes(q) ||
        (p.client_name || '').toLowerCase().includes(q)
      if (!matches) return false
    }
    if (clientFilter && p.client_name !== clientFilter) return false
    if (billingFilter && p.billing_type !== billingFilter) return false
    if (statusFilter && p.status !== statusFilter) return false
    return true
  })

  function toggleColumn(col: string) {
    setSelectedColumns((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]))
  }

  async function handleDownload() {
    if (visible.length === 0) return
    setDownloading(true)
    setError(null)
    try {
      await downloadProjectStatement({
        projectIds: visible.map((p) => p.id),
        columns: selectedColumns,
        format: exportFormat,
      })
      setShowDownloadPanel(false)
    } catch (e: any) {
      setError(e.message || 'Failed to download statement')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar showBack={false} title="Projects & Invoices" subtitle="Manage all projects and their financial summaries." />
      <div className="p-8 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            {projects.length > 0 && (
              <>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by project name, number, or client…"
                  className="w-72 bg-white shadow-card rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                />
                <select
                  value={clientFilter}
                  onChange={(e) => setClientFilter(e.target.value)}
                  className="bg-white shadow-card rounded-full px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  <option value="">All Clients</option>
                  {distinctClients.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <select
                  value={billingFilter}
                  onChange={(e) => setBillingFilter(e.target.value)}
                  className="bg-white shadow-card rounded-full px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  <option value="">All Billing Types</option>
                  {distinctBillingTypes.map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-white shadow-card rounded-full px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  <option value="">All Statuses</option>
                  {distinctStatuses.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                {(clientFilter || billingFilter || statusFilter || search) && (
                  <button
                    onClick={() => { setClientFilter(''); setBillingFilter(''); setStatusFilter(''); setSearch('') }}
                    className="text-xs font-medium text-slate-500 hover:text-slate-700 px-2"
                  >
                    Clear filters
                  </button>
                )}
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {projects.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setShowDownloadPanel((v) => !v)}
                  className="text-sm font-medium bg-white border border-slate-200 text-slate-700 px-4 py-2.5 rounded-full hover:bg-slate-50"
                >
                  ⬇ Download ({visible.length})
                </button>
                {showDownloadPanel && (
                  <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-2xl shadow-card p-4 z-20 space-y-4">
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                        Columns to include
                      </p>
                      <div className="space-y-1.5 max-h-40 overflow-y-auto">
                        {EXPORT_COLUMNS.map((col) => (
                          <label key={col} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selectedColumns.includes(col)}
                              onChange={() => toggleColumn(col)}
                            />
                            {col}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Format</p>
                      <select
                        value={exportFormat}
                        onChange={(e) => setExportFormat(e.target.value as 'pdf' | 'excel' | 'csv')}
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                      >
                        <option value="pdf">PDF</option>
                        <option value="excel">Excel</option>
                        <option value="csv">CSV</option>
                      </select>
                    </div>
                    <p className="text-xs text-slate-400">
                      Exports exactly the {visible.length} project{visible.length === 1 ? '' : 's'} currently
                      matching your search and filters above.
                    </p>
                    <button
                      onClick={handleDownload}
                      disabled={downloading || selectedColumns.length === 0 || visible.length === 0}
                      className="w-full text-sm font-medium bg-brand-600 text-white px-4 py-2.5 rounded-full hover:bg-brand-700 disabled:opacity-50"
                    >
                      {downloading ? 'Preparing…' : 'Download'}
                    </button>
                  </div>
                )}
              </div>
            )}
            <button
              onClick={() => navigate('/invoice/standalone/new')}
              className="text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white px-5 py-2.5 rounded-full"
            >
              + New Standalone Invoice
            </button>
            <button
              onClick={() => { /* TODO: project creation requires a client + billing-type picker; not yet wired up */ }}
              title="Project creation form not implemented yet"
              disabled
              className="text-sm font-medium bg-slate-200 text-slate-400 cursor-not-allowed px-5 py-2.5 rounded-full"
            >
              + New Project
            </button>
          </div>
        </div>

        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}

        {loading ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : projects.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">
            No projects found. Convert an approved estimation into a project to get started.
          </Card>
        ) : visible.length === 0 ? (
          <Card className="text-center py-10 text-sm text-slate-400">
            No projects match your search and filters.
          </Card>
        ) : (
          <Card className="!p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 text-xs uppercase tracking-wider">
                    <th className="py-3 px-5 font-medium">Project</th>
                    <th className="py-3 px-5 font-medium">Client</th>
                    <th className="py-3 px-5 font-medium">Number</th>
                    <th className="py-3 px-5 font-medium">Billing</th>
                    <th className="py-3 px-5 font-medium text-right">Contract Value</th>
                    <th className="py-3 px-5 font-medium text-center">Status</th>
                    <th className="py-3 px-5 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {visible.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-800">{p.project_name}</td>
                      <td className="py-3.5 px-5 text-slate-600">
                        {p.client_name || <span className="text-slate-300 italic">Unspecified</span>}
                      </td>
                      <td className="py-3.5 px-5 text-slate-500 font-mono text-xs">{p.project_number}</td>
                      <td className="py-3.5 px-5">
                        {p.billing_type ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide bg-indigo-50 text-indigo-700">
                            {p.billing_type}
                          </span>
                        ) : (
                          <span className="text-slate-300 text-xs">—</span>
                        )}
                      </td>
                      <td className="py-3.5 px-5 text-right font-semibold text-slate-800 tabular-nums">
                        {money(p.contract_value)}
                      </td>
                      <td className="py-3.5 px-5 text-center">
                        <StatusBadge status={p.status} />
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => navigate(`/invoice/projects/${p.id}`)}
                          className="text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 hover:text-brand-700 px-4 py-2 rounded-full transition-colors"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {standaloneInvoices.length > 0 && (
          <Card title="Standalone Invoices">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 text-xs uppercase tracking-wider">
                    <th className="py-3 px-5 font-medium">Invoice</th>
                    <th className="py-3 px-5 font-medium">Client</th>
                    <th className="py-3 px-5 font-medium text-right">Total Payable</th>
                    <th className="py-3 px-5 font-medium text-center">Status</th>
                    <th className="py-3 px-5 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {standaloneInvoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-800 font-mono text-xs">{inv.invoice_number || 'DRAFT'}</td>
                      <td className="py-3.5 px-5 text-slate-600">
                        {inv.client_name || <span className="text-slate-300 italic">Unspecified</span>}
                      </td>
                      <td className="py-3.5 px-5 text-right font-semibold text-slate-800 tabular-nums">
                        {money(inv.total_payable)}
                      </td>
                      <td className="py-3.5 px-5 text-center">
                        <StatusBadge status={inv.status} />
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => navigate(`/invoice/standalone/${inv.id}`)}
                          className="text-xs font-medium text-brand-600 bg-brand-50 hover:bg-brand-100 hover:text-brand-700 px-4 py-2 rounded-full transition-colors"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
