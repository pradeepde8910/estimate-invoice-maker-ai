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

export interface ProjectStructure {
  detected: boolean
  structure_type: string
  source_term: string | null
  confidence: number
}

export interface ProjectUnit {
  id: string
  parent_id: string | null
  label: string
  source_term: string | null
  semantic_type: string
  sequence: number
  classification: {
    method: string
    confidence: number
  }
  relevance: {
    estimation: boolean
    billing: boolean
    reporting: boolean
  }
  source: {
    evidence: string
  }
  requirements: Requirement[]
}

export interface TaskEstimate {
  task: string
  role_key: string
  role_label: string
  hours: number
  cost: number
}

export interface RequirementEstimate {
  requirement_id: string
  title: string
  scope_status: 'IN_SCOPE' | 'OUT_OF_SCOPE'
  hours: number
  cost: number
  category: string
  adjustment_reason: string
  implementation_tasks: TaskEstimate[]
}

export interface UnitEstimate {
  unit_id: string
  label: string
  semantic_type: string
  billing: { is_billing_unit: boolean }
  estimate: { hours: number; cost: number }
  requirement_estimates: RequirementEstimate[]
}

export interface TeamMember {
  role_key: string
  count: number
  billing_status: 'BILLABLE' | 'NON_BILLABLE'
  justification: string
}

export interface Phase {
  name: string
  duration_weeks: number
  description: string
}

export interface WebSearchItem {
  query: string
  service_name: string
  service_category: string
  cost_type: string
  configuration?: {
    tier?: string
    quantity?: number
    unit?: string
    usage_assumption?: string
  }
  billing_model?: string
  monthly_cost_inr: number | null
  cost_basis?: string
  sources: string[]
}

export interface QuotationValidation {
  is_valid: boolean
  error_count: number
  warning_count: number
  errors: string[]
  warnings: string[]
}

export interface JobResult {
  client_name: string
  client_info?: {
    company_name?: string | null
    contact_person?: string | null
    email?: string | null
    phone?: string | null
    billing_address?: string | null
    gstin?: string | null
    status?: string | null
  }
  project_name: string
  project_type: string
  project_description: string
  tech_stack_suggested: string[]
  project_structure?: ProjectStructure
  project_units?: ProjectUnit[]
  unit_estimates?: UnitEstimate[]
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
  estimation_assumptions: string[]
  web_search_items: WebSearchItem[]
  has_brd: boolean
  has_srs: boolean
  has_quotation: boolean
  quotation_validation?: QuotationValidation
  status?: string
  converted_project_id?: string | null
  version?: number
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

export type InvoiceStatus = 'Draft' | 'Sent' | 'Paid' | 'Partially Paid' | 'Overdue' | 'Cancelled'

export interface InvoiceMeta {
  invoice_number: string
  invoice_date: string
  due_date: string
  tax_percentage: number
  subtotal: number
  tax_amount: number
  total_due: number
  amount_paid: number
  paid_on: string | null
  client_name: string
  project_name: string
  status: InvoiceStatus
}

export interface Financials {
  contract_value: number;
  total_billed: number;
  total_paid: number;
  remaining_contract: number;
  reserved_contingency: number;
  outstanding: number;
  total_subtotal: number;
  total_invoiced: number;
  total_tds: number;
  total_payable: number;
  total_collected: number;
}

export interface ProjectMilestone {
  id: string;
  name: string;
  amount: number;
  due_date: string;
  status: string;
}

export interface CommercialComponent {
  id: string;
  name: string;
  amount: number;
  billed_amount: number;
  component_type: string;
  billing_policy: string;
  status: string;
}

export interface ProjectFinancialSummary {
  project_id: string;
  project_name: string;
  project_number: string;
  financials: Financials;
  milestones: ProjectMilestone[];
  components: CommercialComponent[];
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
  version: number
}

export interface ClientGroup {
  client_name: string
  estimations: DocumentSummary[]
  estimation_count: number
  latest_modified: string
}

export interface RateCard {
  [key: string]: { rate_per_hour: number; label: string; is_custom?: boolean }
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
  upi_id: string
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
  recent_invoices: DocumentSummary[]
}
