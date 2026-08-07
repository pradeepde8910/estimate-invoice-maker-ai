export interface RoleEstimate {
  role_key: string
  role_label: string
  hours: number
  rate_per_hour: number
  total_cost: number
}

export interface CategoryBreakdown {
  category: string
  requirements_count: number
  total_hours: number
  total_cost: number
  items: any[]
}

export interface Requirement {
  id: string
  title: string
  description: string
  category: string
  priority: string
  complexity: string
  estimated_hours: number
  required_role: string
  technologies: string[]
}

export interface TeamMember {
  role_key: string
  count: number
  justification: string
}

export interface Phase {
  name: string
  duration_weeks: number
  description: string
}

export interface WebSearchItem {
  query: string
  answer: string
  estimated_cost: number | null
  cost_type: string
  sources: string[]
}

export interface JobResult {
  client_name: string
  project_name: string
  project_type: string
  project_description: string
  tech_stack_suggested: string[]
  requirements: Requirement[]
  assumptions: string[]
  risks: string[]
  out_of_scope: string[]
  role_estimates: RoleEstimate[]
  category_breakdown: CategoryBreakdown[]
  total_development_hours: number
  total_development_cost: number
  infrastructure_cost_monthly: number
  third_party_licenses_monthly: number
  contingency_percentage: number
  contingency_amount: number
  grand_total: number
  timeline_weeks: number
  team_composition: TeamMember[]
  phases: Phase[]
  web_search_items: WebSearchItem[]
  has_brd: boolean
  has_srs: boolean
  has_quotation: boolean
}

export type JobStatus = 'queued' | 'running' | 'complete' | 'failed' | 'cancelled'

export interface Job {
  id: string
  status: JobStatus
  step_index: number
  steps: string[]
  log: string[]
  error: string | null
  source_name: string
  result: JobResult | null
  base_name: string | null
  created_at: string | null
}

export type InvoiceStatus = 'Draft' | 'Sent' | 'Paid' | 'Overdue' | 'Cancelled'

export interface InvoiceMeta {
  invoice_number: string
  invoice_date: string
  due_date: string
  tax_percentage: number
  subtotal: number
  tax_amount: number
  total_due: number
  client_name: string
  project_name: string
  status: InvoiceStatus
}

export interface DocumentSummary {
  base_name: string
  project_name: string
  client_name: string
  files: Record<string, string>
  modified: string
  grand_total: number | null
  timeline_weeks: number | null
  has_invoice: boolean
  invoice_meta: InvoiceMeta | null
}

export interface ClientGroup {
  client_name: string
  estimations: DocumentSummary[]
  estimation_count: number
  latest_modified: string
}

export interface RateCard {
  [key: string]: { rate_per_hour: number; label: string }
}

export interface OrganizationProfile {
  name: string
  tagline: string
  address: string
  email: string
  phone: string
  website: string
  gstin: string
  registration_number: string
  certifications: string
  signatory_name: string
  signatory_title: string
  bank_name: string
  bank_account_number: string
  bank_ifsc: string
  bank_branch: string
  logo_path: string | null
  signature_path: string | null
  seal_path: string | null
  invoice_terms: string
}

export interface Analytics {
  total_estimations: number
  today_count: number
  month_count: number
  total_project_value: number
  average_estimation_value: number
  invoiced_count: number
  revenue_paid: number
  revenue_pending: number
  status_overview: Record<string, number>
  recent: DocumentSummary[]
}
