import type { Job, DocumentSummary, ClientGroup, RateCard, OrganizationProfile, InvoiceMeta, Analytics, InvoiceStatus } from './types'

const BASE = '/api'

const originalFetch = window.fetch
async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = localStorage.getItem('pixous_auth_token')
  const headers = new Headers(init?.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await originalFetch(input, { ...init, headers })
  if (res.status === 401) {
    localStorage.removeItem('pixous_auth_token')
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

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text || `Request failed (${res.status})`)
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
  // Open the tab synchronously (inside the click handler's call stack) so
  // popup blockers don't treat the later async redirect as an unsolicited popup.
  const tab = window.open('', '_blank', 'noopener,noreferrer')
  try {
    const res = await fetch(documentPdfUrl(baseName, docType))
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new ApiError(res.status, text || `Request failed (${res.status})`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    if (tab) tab.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e) {
    tab?.close()
    throw e
  }
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
  status: InvoiceStatus
): Promise<{ invoice_meta: InvoiceMeta; invoice_html: string }> {
  const res = await fetch(`${BASE}/estimations/${encodeURIComponent(baseName)}/invoice/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
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
  localStorage.setItem('pixous_auth_token', data.token)
  return data
}

export function logout() {
  localStorage.removeItem('pixous_auth_token')
  window.location.href = '/login'
}

