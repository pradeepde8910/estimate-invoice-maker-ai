import type { Job, DocumentSummary, ClientGroup, RateCard, OrganizationProfile, InvoiceMeta, Analytics, InvoiceStatus } from './types'

const BASE = '/api'

const originalFetch = window.fetch
async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = sessionStorage.getItem('pixous_auth_token')
  const headers = new Headers(init?.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await originalFetch(input, { ...init, headers })
  if (res.status === 401) {
    sessionStorage.removeItem('pixous_auth_token')
    if (!window.location.pathname.endsWith('/login')) {
      window.location.href = '/login'
    }
  }
  return res
}
const fetch = authFetch

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Shared by every error path below (both json() and the blob/download
// helpers) so a FastAPI/pydantic validation error — an array of
// {type, loc, msg, ctx} objects — always reads as a plain sentence instead
// of a raw JSON dump, regardless of which function hit the failing request.
function extractErrorMessage(text: string, fallbackStatus: number): string {
  try {
    const parsed = JSON.parse(text)
    if (parsed.detail) {
      if (typeof parsed.detail === 'string') {
        return parsed.detail
      }
      if (Array.isArray(parsed.detail) && parsed.detail.every((d: any) => d?.msg)) {
        return parsed.detail.map((d: any) => String(d.msg).replace(/^Value error, /, '')).join('; ')
      }
      return JSON.stringify(parsed.detail)
    }
    if (parsed.message) return parsed.message
  } catch {
    // not JSON, fall through to raw text
  }
  return text || `Request failed (${fallbackStatus})`
}

async function throwApiError(res: Response): Promise<never> {
  const text = await res.text().catch(() => res.statusText)
  throw new ApiError(res.status, extractErrorMessage(text, res.status))
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    await throwApiError(res)
  }
  return res.json()
}

export async function createJob(input: {
  file?: File
  url?: string
  text?: string
  generate_brd?: boolean
  generate_srs?: boolean
}): Promise<{ job_id: string }> {
  const form = new FormData()
  if (input.file) form.append('file', input.file)
  if (input.url) form.append('url', input.url)
  if (input.text) form.append('text', input.text)
  form.append('generate_brd', String(input.generate_brd ?? true))
  form.append('generate_srs', String(input.generate_srs ?? true))
  const res = await fetch(`${BASE}/jobs`, { method: 'POST', body: form })
  return json(res)
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${jobId}`)
  return json(res)
}

export async function cancelJob(jobId: string): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/jobs/${jobId}/cancel`, { method: 'POST' })
  return json(res)
}

export async function getJobDocument(jobId: string, docType: 'quotation' | 'brd' | 'srs'): Promise<string> {
  const res = await fetch(`${BASE}/jobs/${jobId}/document/${docType}`)
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}

export async function listDocuments(): Promise<{ documents: DocumentSummary[] }> {
  const res = await fetch(`${BASE}/documents`)
  return json(res)
}

export async function listClients(): Promise<{ clients: ClientGroup[] }> {
  const res = await fetch(`${BASE}/clients`)
  return json(res)
}

export async function listDbClients(): Promise<{ clients: any[] }> {
  const res = await fetch(`${BASE}/db-clients`)
  return json(res)
}

// V2's own client roster (backs Invoice.client_id / Project.client_id) — a
// distinct SQLite database from v1's /db-clients above, so the two endpoints'
// client ids are NOT interchangeable.
export async function listMasterClients(): Promise<any[]> {
  const res = await fetch(`${BASE}/master/clients`)
  return json(res)
}

export async function createMasterClient(data: {
  company_name?: string | null
  contact_person?: string | null
  email?: string | null
  phone?: string | null
  gstin?: string | null
  billing_address?: string | null
}): Promise<any> {
  const res = await fetch(`${BASE}/master/clients`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return json(res)
}

export async function createManualEstimation(payload: {
  client_name: string
  project_name: string
  line_items: { description: string; quantity: number; rate: number }[]
}): Promise<{ base_name: string }> {
  const res = await fetch(`${BASE}/estimations/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return json(res)
}

export async function patchEstimation(
  baseName: string,
  payload: { project_name?: string; timeline_weeks?: number; grand_total?: number; status?: string; version: number }
): Promise<{ id: string; project_name: string; timeline_weeks: number; grand_total: number; version: number; updated_at: string }> {
  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return json(res)
}

export async function patchEstimationClient(
  baseName: string,
  payload: {
    company_name?: string | null
    contact_person?: string | null
    email?: string | null
    phone?: string | null
    billing_address?: string | null
    gstin?: string | null
    status?: string | null
  }
): Promise<{ status: string; client_id: string }> {
  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}/client`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return json(res)
}

export async function deleteEstimation(baseName: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}`, { method: 'DELETE' })
  return json(res)
}

export async function deleteInvoice(invoiceNumber: string): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/invoices/${encodeURIComponent(invoiceNumber)}`, { method: 'DELETE' })
  return json(res)
}

export async function getEstimationData(baseName: string): Promise<any> {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(baseName)}/data`)
  return json(res)
}

export async function getDocumentFile(baseName: string, docType: 'quotation' | 'brd' | 'srs' | 'invoice'): Promise<string> {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(baseName)}/${docType}`)
  if (!res.ok) throw new Error(await res.text())
  return res.text()
}

export async function updateDocumentContent(
  baseName: string,
  docType: 'quotation' | 'brd' | 'srs' | 'invoice',
  content: string
): Promise<{ content: string }> {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(baseName)}/${docType}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  return json(res)
}

export function documentPdfUrl(baseName: string, docType: string) {
  return `${BASE}/documents/${encodeURIComponent(baseName)}/${docType}/pdf`
}

export async function openDocumentPdf(baseName: string, docType: string) {
  const res = await fetch(documentPdfUrl(baseName, docType))
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${baseName}_${docType}.pdf`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

async function downloadBlobAs(res: Response, filename: string) {
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  if (blob.size === 0) {
    throw new ApiError(500, 'The server returned an empty file.')
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

// Complete multi-sheet estimation workbook (overview, timeline with Gantt
// chart, cost breakdowns, requirements, task-level detail, team,
// infrastructure/license costs, risks/assumptions — each with charts where
// there's something worth visualizing).
export async function downloadEstimationExcel(baseName: string) {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(baseName)}/excel`)
  await downloadBlobAs(res, `${baseName}_estimation.xlsx`)
}

// Standalone timeline-only workbook (phases + Gantt chart) — for when just
// the schedule is needed rather than the full estimation.
export async function downloadEstimationTimelineExcel(baseName: string) {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(baseName)}/timeline/excel`)
  await downloadBlobAs(res, `${baseName}_timeline.xlsx`)
}

export async function downloadInvoicePdf(invoiceId: string) {
  const res = await fetch(`${BASE}/invoices/${invoiceId}/pdf`)
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `invoice_${invoiceId}.pdf`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

// Downloads a combined statement of every invoice in [fromDate, toDate] (YYYY-MM-DD),
// optionally scoped to one project. `format` matches the backend's ExportFormat enum.
export async function downloadInvoiceStatement(
  fromDate: string,
  toDate: string,
  opts: { projectId?: string; format?: 'csv' | 'excel' | 'pdf' } = {}
) {
  const format = opts.format || 'pdf'
  const res = await fetch(`${BASE}/reports/INVOICE/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters: {
        project_id: opts.projectId || null,
        from_date: fromDate,
        to_date: toDate,
      },
      format,
    }),
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const extension = format === 'excel' ? 'xlsx' : format
  a.download = `invoice_statement_${fromDate}_to_${toDate}.${extension}`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

// Config-driven project export: exact set of project_ids (whatever's
// currently filtered on screen), a caller-chosen column subset, and format.
export async function downloadProjectStatement(opts: {
  projectIds: string[]
  columns?: string[]
  format?: 'csv' | 'excel' | 'pdf'
}) {
  const format = opts.format || 'pdf'
  const res = await fetch(`${BASE}/reports/PROJECT/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters: { project_ids: opts.projectIds },
      selected_columns: opts.columns && opts.columns.length > 0 ? opts.columns : null,
      format,
    }),
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const extension = format === 'excel' ? 'xlsx' : format
  a.download = `projects_statement.${extension}`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export interface ReportFilters {
  client_id?: string | null
  client_ids?: string[] | null
  project_id?: string | null
  project_ids?: string[] | null
  from_date?: string | null
  to_date?: string | null
  statuses?: string[] | null
  billing_type?: string | null
}

// Generic entry point over the backend's report engine (PROJECT, INVOICE,
// PAYMENT, OUTSTANDING, MILESTONE — see backend/app/api/report.py) — the
// single place every report/export UI in the app should route through,
// rather than each screen hand-rolling its own fetch/blob/download dance.
export async function exportReport(
  reportType: 'PROJECT' | 'INVOICE' | 'PAYMENT' | 'OUTSTANDING' | 'MILESTONE',
  filters: ReportFilters,
  format: 'csv' | 'excel' | 'pdf',
  selectedColumns?: string[] | null,
  filenameHint?: string
) {
  const res = await fetch(`${BASE}/reports/${reportType}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filters,
      format,
      selected_columns: selectedColumns && selectedColumns.length > 0 ? selectedColumns : null,
    }),
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  const blob = await res.blob()
  if (blob.size === 0) {
    throw new ApiError(500, 'The server returned an empty file.')
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const extension = format === 'excel' ? 'xlsx' : format
  const base = filenameHint || reportType.toLowerCase()
  a.download = `${base}.${extension}`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export async function getInvoiceDetails(invoiceId: string): Promise<any> {
  const res = await fetch(`${BASE}/invoices/${invoiceId}`)
  return json(res)
}

export async function getRateCard(): Promise<{ rates: RateCard }> {
  const res = await fetch(`${BASE}/rate-card`)
  return json(res)
}

export async function updateRateCard(rates: RateCard): Promise<{ rates: RateCard }> {
  const res = await fetch(`${BASE}/rate-card`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rates }),
  })
  return json(res)
}

export async function getOrganization(): Promise<{ profile: OrganizationProfile }> {
  const res = await fetch(`${BASE}/organization`)
  return json(res)
}

export async function updateOrganization(
  profile: Omit<OrganizationProfile, 'logo_path' | 'signature_path' | 'seal_path'>
): Promise<{ profile: OrganizationProfile }> {
  const res = await fetch(`${BASE}/organization`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  return json(res)
}

export async function uploadOrganizationAsset(
  slot: 'logo' | 'signature' | 'seal',
  file: File
): Promise<{ profile: OrganizationProfile }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/organization/${slot}`, { method: 'POST', body: form })
  return json(res)
}

export async function deleteOrganizationAsset(
  slot: 'logo' | 'signature' | 'seal'
): Promise<{ profile: OrganizationProfile }> {
  const res = await fetch(`${BASE}/organization/${slot}`, { method: 'DELETE' })
  return json(res)
}

export async function applyBrandingHistory(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/organization/apply-branding-history`, { method: 'POST' })
  return json(res)
}



export async function generateInvoice(
  baseName: string,
  opts: { tax_percentage: number; due_days: number }
): Promise<{ invoice_html: string; invoice_meta: InvoiceMeta }> {
  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}/invoice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(opts),
  })
  return json(res)
}

export async function getInvoice(baseName: string): Promise<{ invoice_html: string; invoice_meta: InvoiceMeta | null }> {
  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}/invoice`)
  return json(res)
}

export async function updateInvoiceStatus(
  baseName: string,
  status: InvoiceStatus,
  amountPaid?: number,
  paidOn?: string
): Promise<{ invoice_meta: InvoiceMeta; invoice_html: string }> {
  const body: any = { status }
  if (amountPaid !== undefined) body.amount_paid = amountPaid
  if (paidOn) body.paid_on = paidOn

  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}/invoice/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return json(res)
}

export async function getAnalytics(): Promise<Analytics> {
  const res = await fetch(`${BASE}/analytics`)
  return json(res)
}

export function docDownloadUrl(baseName: string, docType: string) {
  return `${BASE}/documents/${encodeURIComponent(baseName)}/${docType}`
}

export async function login(password: string, username: string = 'admin'): Promise<{ token: string }> {
  // Use originalFetch here to bypass authentication middleware checks
  const res = await originalFetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text || `Login failed (${res.status})`)
  }
  const data = await res.json()
  sessionStorage.setItem('pixous_auth_token', data.token)
  return data
}

export function logout() {
  sessionStorage.removeItem('pixous_auth_token')
  window.location.href = '/login'
}

export async function validateSession(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/validate`)
    return res.ok
  } catch {
    return false
  }
}




// --- V2 Financial API Endpoints ---
export async function getProjectSummary(projectId: string): Promise<any> {
  const res = await fetch(`${BASE}/projects/${projectId}/summary`);
  return json(res);
}

export async function listInvoices(projectId: string): Promise<any> {
  const res = await fetch(`${BASE}/projects/${projectId}/invoices`);
  return json(res);
}

export interface BillingClassificationMatch {
  id: string
  category: string
  description: string
  item_type: string
  hsn_sac_code: string
  hsn_sac_type: string
  gst_rate: number
  score: number
}

export async function matchBillingClassifications(description: string, limit = 5): Promise<BillingClassificationMatch[]> {
  const res = await fetch(`${BASE}/master/billing-classifications/match?description=${encodeURIComponent(description)}&limit=${limit}`)
  return json(res)
}

export async function createInvoice(projectId: string, data: any): Promise<any> {
  const res = await fetch(`${BASE}/invoices/projects/${projectId}/invoices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

export async function listStandaloneInvoices(): Promise<any[]> {
  const res = await fetch(`${BASE}/invoices/standalone`);
  return json(res);
}

export async function createStandaloneInvoice(data: any): Promise<any> {
  const res = await fetch(`${BASE}/invoices/standalone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

export async function getInvoiceV2(invoiceId: string): Promise<any> {
  const res = await fetch(`${BASE}/invoices/${invoiceId}`);
  return json(res);
}

export async function updateInvoiceStatusV2(invoiceId: string, status: string): Promise<any> {
  const res = await fetch(`${BASE}/invoices/${invoiceId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  return json(res);
}

export async function recordPayment(projectId: string, invoiceId: string, data: any): Promise<any> {
  const res = await fetch(`${BASE}/payments/${projectId}/invoices/${invoiceId}/payments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

// Records a payment that already happened outside the app (cash, bank transfer, UPI, cheque)
// in one atomic step — goes straight to SUCCESS instead of the initiate/processing/success
// gateway lifecycle `recordPayment` above drives, which is unnecessary for manual entry.
export async function recordManualPayment(
  projectId: string,
  invoiceId: string,
  data: { amount: number; payment_method: string; payment_date?: string; transaction_reference?: string; remarks?: string }
): Promise<any> {
  const res = await fetch(`${BASE}/payments/${projectId}/invoices/${invoiceId}/payments/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

export async function listInvoicePayments(projectId: string, invoiceId: string): Promise<any[]> {
  const res = await fetch(`${BASE}/payments/${projectId}/invoices/${invoiceId}/payments`);
  return json(res);
}

export async function listProjects(): Promise<any> {
  const res = await fetch(`${BASE}/projects`);
  return json(res);
}

export async function createProject(data: any) {
  const res = await fetch(`${BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

export async function convertEstimationToProject(estimationId: string): Promise<any> {
  const res = await fetch(`${BASE}/projects/estimations/${estimationId}/convert`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  return json(res);
}

// --- Billing Classifications ---
export async function listBillingClassifications(): Promise<any[]> {
  const res = await fetch(`${BASE}/master/billing-classifications`);
  return json<any[]>(res);
}

export async function matchBillingClassification(description: string): Promise<any[]> {
  const res = await fetch(`${BASE}/master/billing-classifications/match?description=${encodeURIComponent(description)}`);
  return json<any[]>(res);
}

export async function createBillingClassification(data: any): Promise<any> {
  const res = await fetch(`${BASE}/master/billing-classifications`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

export async function updateBillingClassification(id: string, data: any): Promise<any> {
  const res = await fetch(`${BASE}/master/billing-classifications/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return json(res);
}

export async function deleteBillingClassification(id: string): Promise<any> {
  const res = await fetch(`${BASE}/master/billing-classifications/${id}`, {
    method: 'DELETE',
  });
  return json(res);
}

export async function getBillingPreview(projectId: string): Promise<any> {
  const res = await fetch(`${BASE}/projects/${projectId}/billing-preview`);
  return json(res);
}

// --- Resource & Capability Catalog ---
const RC_BASE = `${BASE}/master/resource-catalog`

export async function listCapabilities(): Promise<any[]> {
  return json(await fetch(`${RC_BASE}/capabilities`))
}
export async function createCapability(data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/capabilities`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function updateCapability(id: string, data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/capabilities/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function deleteCapability(id: string): Promise<any> {
  return json(await fetch(`${RC_BASE}/capabilities/${id}`, { method: 'DELETE' }))
}

export async function listProviders(): Promise<any[]> {
  return json(await fetch(`${RC_BASE}/providers`))
}
export async function createProvider(data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/providers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function updateProvider(id: string, data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/providers/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function deleteProvider(id: string): Promise<any> {
  return json(await fetch(`${RC_BASE}/providers/${id}`, { method: 'DELETE' }))
}

export async function listTechnologyModels(): Promise<any[]> {
  return json(await fetch(`${RC_BASE}/models`))
}
export async function createTechnologyModel(data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/models`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function updateTechnologyModel(id: string, data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/models/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function deleteTechnologyModel(id: string): Promise<any> {
  return json(await fetch(`${RC_BASE}/models/${id}`, { method: 'DELETE' }))
}

export async function addModelFeature(modelId: string, data: { feature_key: string; feature_value: string }): Promise<any> {
  return json(await fetch(`${RC_BASE}/models/${modelId}/features`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function deleteModelFeature(id: string): Promise<any> {
  return json(await fetch(`${RC_BASE}/features/${id}`, { method: 'DELETE' }))
}

export async function addPricingRule(modelId: string, data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/models/${modelId}/pricing`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function updatePricingRule(id: string, data: any): Promise<any> {
  return json(await fetch(`${RC_BASE}/pricing/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }))
}
export async function deletePricingRule(id: string): Promise<any> {
  return json(await fetch(`${RC_BASE}/pricing/${id}`, { method: 'DELETE' }))
}
