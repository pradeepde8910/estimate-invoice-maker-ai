import { useEffect, useMemo, useState } from 'react'
import { clientDisplayLabel } from '../utils/clientLabel'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { listMasterClients, listProjects, exportReport } from '../api/client'
import type { ReportFilters } from '../api/client'

type ReportType = 'PROJECT' | 'INVOICE' | 'PAYMENT' | 'OUTSTANDING' | 'MILESTONE'
type ExportFormat = 'csv' | 'excel' | 'pdf'

interface ReportConfig {
  label: string
  description: string
  columns: string[]
  hasClientFilter: boolean
  hasProjectFilter: boolean
  dateMode: 'range' | 'as-of' | 'none'
  dateLabel: string
  statusOptions: string[] | null // null = no status filter for this report
  hasBillingTypeFilter: boolean
}

const REPORT_CONFIGS: Record<ReportType, ReportConfig> = {
  PROJECT: {
    label: 'Projects',
    description: 'Every project matching your filters — contract value, billing type, status.',
    columns: ['Project Number', 'Project Name', 'Client Name', 'Billing Type', 'Status', 'Contract Value', 'Created At'],
    hasClientFilter: true,
    hasProjectFilter: false,
    dateMode: 'range',
    dateLabel: 'Created',
    statusOptions: null, // populated dynamically from live projects (statuses aren't a fixed enum)
    hasBillingTypeFilter: true,
  },
  INVOICE: {
    label: 'Invoices',
    description: 'Invoices raised — amounts, GST, status, payment status.',
    columns: ['Invoice Number', 'Project Name', 'Client Name', 'Billing Model', 'Billing Sources', 'Invoice Date', 'Due Date', 'Status', 'Payment Status', 'Subtotal', 'Gross Amount', 'Total Payable'],
    hasClientFilter: true,
    hasProjectFilter: true,
    dateMode: 'range',
    dateLabel: 'Invoice Date',
    statusOptions: ['DRAFT', 'ISSUED', 'CANCELLED'],
    hasBillingTypeFilter: false,
  },
  PAYMENT: {
    label: 'Payments',
    description: 'Payment history — every recorded payment, including a specific client’s.',
    columns: ['Payment Reference', 'Invoice Number', 'Project Name', 'Client Name', 'Payment Method', 'Status', 'Initiated At', 'Received At', 'Amount'],
    hasClientFilter: true,
    hasProjectFilter: true,
    dateMode: 'range',
    dateLabel: 'Received',
    statusOptions: ['INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED'],
    hasBillingTypeFilter: false,
  },
  OUTSTANDING: {
    label: 'Outstanding',
    description: 'Issued invoices with a balance still due, as of a chosen date.',
    columns: ['Invoice Number', 'Project Name', 'Client Name', 'Invoice Date', 'Total Payable', 'Collected (As Of)', 'Outstanding (As Of)'],
    hasClientFilter: true,
    hasProjectFilter: true,
    dateMode: 'as-of',
    dateLabel: 'As Of',
    statusOptions: null,
    hasBillingTypeFilter: false,
  },
  MILESTONE: {
    label: 'Milestones',
    description: 'Project delivery milestones — due dates, amounts, billing status.',
    columns: ['Milestone Name', 'Project Name', 'Client Name', 'Status', 'Due Date', 'Amount'],
    hasClientFilter: true,
    hasProjectFilter: true,
    dateMode: 'range',
    dateLabel: 'Due Date',
    statusOptions: ['PENDING', 'IN_PROGRESS', 'PARTIALLY_BILLED', 'BILLED', 'COMPLETED'],
    hasBillingTypeFilter: false,
  },
}

const REPORT_ORDER: ReportType[] = ['INVOICE', 'PAYMENT', 'OUTSTANDING', 'PROJECT', 'MILESTONE']

function todayInputValue(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function ExportCenter() {
  const [reportType, setReportType] = useState<ReportType>('INVOICE')
  const [clients, setClients] = useState<any[]>([])
  const [projects, setProjects] = useState<any[]>([])
  const [clientId, setClientId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [asOfDate, setAsOfDate] = useState(todayInputValue())
  const [statuses, setStatuses] = useState<string[]>([])
  const [billingType, setBillingType] = useState('')
  const [selectedColumns, setSelectedColumns] = useState<string[]>(REPORT_CONFIGS.INVOICE.columns)
  const [format, setFormat] = useState<ExportFormat>('pdf')
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const config = REPORT_CONFIGS[reportType]

  useEffect(() => {
    listMasterClients().then(setClients).catch(() => {})
    listProjects().then(setProjects).catch(() => {})
  }, [])

  // Reset filters that don't make sense for the newly chosen report type, and
  // default the column picker to that report's full column set.
  function switchReportType(next: ReportType) {
    setReportType(next)
    setStatuses([])
    setBillingType('')
    setSelectedColumns(REPORT_CONFIGS[next].columns)
    setError(null)
  }

  const distinctProjectStatuses = useMemo(
    () => Array.from(new Set(projects.map((p) => p.status).filter(Boolean))).sort(),
    [projects]
  )
  const distinctBillingTypes = useMemo(
    () => Array.from(new Set(projects.map((p) => p.billing_type).filter(Boolean))).sort(),
    [projects]
  )
  const statusOptions = config.statusOptions ?? (reportType === 'PROJECT' ? distinctProjectStatuses : [])

  // Deduplicate clients by label so we don't show the exact same string multiple times
  const uniqueClients = useMemo(() => {
    const map = new Map<string, any>()
    for (const c of clients) {
      const label = clientDisplayLabel(c)
      if (!map.has(label)) {
        map.set(label, { ...c, aggregated_ids: [c.id], display_label: label })
      } else {
        map.get(label).aggregated_ids.push(c.id)
      }
    }
    return Array.from(map.values())
  }, [clients])

  const selectedClientName = useMemo(
    () => uniqueClients.find((c) => c.aggregated_ids.join(',') === clientId)?.display_label ?? null,
    [uniqueClients, clientId]
  )
  const projectsForClient = useMemo(
    () => (clientId ? projects.filter((p) => clientId.includes(p.client_id)) : projects),
    [projects, clientId]
  )

  function handleClientChange(newClientIds: string) {
    setClientId(newClientIds)
    const stillValid = !projectId || projects.some((p) => p.id === projectId && (!newClientIds || newClientIds.includes(p.client_id)))
    if (!stillValid) setProjectId('')
  }

  function toggleStatus(s: string) {
    setStatuses((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]))
  }

  function toggleColumn(col: string) {
    // Re-adding a column appends it to `selectedColumns` at click time, not
    // at its natural position — harmless for the checkboxes themselves
    // (rendered from config.columns, so they never move), but that array's
    // order is exactly what dictates column order in the exported file, so
    // clicking columns out of order would silently scramble the export.
    // handleDownload re-derives the natural order from config.columns
    // before sending, rather than trusting accumulated click order here.
    setSelectedColumns((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]))
  }

  async function handleDownload() {
    setError(null)
    if (config.dateMode === 'range' && fromDate && toDate && fromDate > toDate) {
      setError('"From" date cannot be after "To" date.')
      return
    }
    const filters: ReportFilters = {
      client_ids: clientId ? clientId.split(',') : null,
      project_id: config.hasProjectFilter && projectId ? projectId : null,
      statuses: statuses.length > 0 ? statuses : null,
      billing_type: config.hasBillingTypeFilter && billingType ? billingType : null,
    }
    if (config.dateMode === 'range') {
      filters.from_date = fromDate || null
      filters.to_date = toDate || null
    } else if (config.dateMode === 'as-of') {
      filters.to_date = asOfDate || null
    }

    // Always export columns in the report's natural (displayed) order,
    // regardless of the order they were toggled on in.
    const orderedColumns = config.columns.filter((c) => selectedColumns.includes(c))

    setDownloading(true)
    try {
      await exportReport(reportType, filters, format, orderedColumns, reportType.toLowerCase() + '_export')
    } catch (e: any) {
      setError(e.message || 'Failed to generate export')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar showBack={false} title="Export Center" subtitle="Download any slice of your data — invoices, payments, outstanding balances, projects, or milestones." />
      <div className="p-8 space-y-6 max-w-5xl mx-auto">

        <Card className="!p-0 overflow-hidden">
          <div className="flex flex-wrap divide-x divide-slate-100 border-b border-slate-100">
            {REPORT_ORDER.map((rt) => (
              <button
                key={rt}
                onClick={() => switchReportType(rt)}
                className={`flex-1 min-w-[140px] px-4 py-3 text-sm font-medium transition-colors ${
                  reportType === rt ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {REPORT_CONFIGS[rt].label}
              </button>
            ))}
          </div>
          <div className="px-5 py-3 text-xs text-slate-500">{config.description}</div>
        </Card>

        <Card title="Filters">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {config.hasClientFilter && (
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Client</label>
                <select
                  value={clientId}
                  onChange={(e) => handleClientChange(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  <option value="">All Clients</option>
                  {uniqueClients.map((c) => (
                    <option key={c.display_label} value={c.aggregated_ids.join(',')}>{c.display_label}</option>
                  ))}
                </select>
              </div>
            )}

            {config.hasProjectFilter && (
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Project</label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  <option value="">{selectedClientName ? `All ${selectedClientName} Projects` : 'All Projects'}</option>
                  {projectsForClient.map((p) => (
                    <option key={p.id} value={p.id}>{p.project_name} ({p.project_number})</option>
                  ))}
                </select>
                {selectedClientName && projectsForClient.length === 0 && (
                  <p className="text-xs text-slate-400 mt-1">No projects found for this client.</p>
                )}
              </div>
            )}

            {config.hasBillingTypeFilter && (
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Billing Type</label>
                <select
                  value={billingType}
                  onChange={(e) => setBillingType(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300"
                >
                  <option value="">All Billing Types</option>
                  {distinctBillingTypes.map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </div>
            )}

            {config.dateMode === 'range' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">{config.dateLabel} From</label>
                  <input
                    type="date"
                    value={fromDate}
                    onChange={(e) => setFromDate(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">{config.dateLabel} To</label>
                  <input
                    type="date"
                    value={toDate}
                    onChange={(e) => setToDate(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                  />
                </div>
              </>
            )}

            {config.dateMode === 'as-of' && (
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">As Of Date</label>
                <input
                  type="date"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm"
                />
              </div>
            )}
          </div>

          {statusOptions.length > 0 && (
            <div className="mt-4">
              <label className="block text-xs font-medium text-slate-500 mb-2">Status {statuses.length === 0 && <span className="text-slate-400">(all)</span>}</label>
              <div className="flex flex-wrap gap-2">
                {statusOptions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleStatus(s)}
                    className={`text-xs font-medium px-3 py-1.5 rounded-full transition-colors ${
                      statuses.includes(s) ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {s.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card title="Columns">
          <div className="flex flex-wrap gap-2">
            {config.columns.map((col) => (
              <label
                key={col}
                className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full cursor-pointer transition-colors ${
                  selectedColumns.includes(col) ? 'bg-brand-50 text-brand-700 border border-brand-200' : 'bg-slate-50 text-slate-500 border border-slate-200'
                }`}
              >
                <input
                  type="checkbox"
                  className="hidden"
                  checked={selectedColumns.includes(col)}
                  onChange={() => toggleColumn(col)}
                />
                {col}
              </label>
            ))}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-2">Format</label>
              <div className="flex gap-2">
                {(['pdf', 'excel', 'csv'] as ExportFormat[]).map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFormat(f)}
                    className={`text-sm font-medium px-4 py-2 rounded-full uppercase tracking-wide ${
                      format === f ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col items-end gap-2">
              {error && <div className="text-sm text-coral-600">{error}</div>}
              <button
                onClick={handleDownload}
                disabled={downloading || selectedColumns.length === 0}
                className="text-sm font-medium bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white px-6 py-2.5 rounded-full"
              >
                {downloading ? 'Preparing…' : `⬇ Download ${config.label}`}
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
