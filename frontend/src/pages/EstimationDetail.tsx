import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import EstimationResult from '../components/EstimationResult'
import ClientDetailsEditor from '../components/ClientDetailsEditor'
import LoadingState from '../components/LoadingState'
import { getEstimationData, convertEstimationToProject, patchEstimation } from '../api/client'
import type { JobResult } from '../api/types'

function toJobResult(data: any): JobResult {
  const analysis = data.analysis || {}
  const estimation = data.cost_estimation || {}
  const web = data.web_search_data || {}
  return {
    client_name: data.client_name || analysis.client_name || 'Unspecified Client',
    client_info: data.client_info || null,
    project_name: data.project_name || analysis.project_name || '',
    project_type: analysis.project_type || '',
    project_description: analysis.project_description || '',
    tech_stack_suggested: analysis.tech_stack_suggested || [],
    project_structure: analysis.project_structure,
    project_units: analysis.project_units,
    unit_estimates: estimation.unit_estimates,
    requirements: analysis.requirements || [],
    assumptions: analysis.assumptions || [],
    risks: analysis.risks || [],
    out_of_scope: analysis.out_of_scope || [],
    role_estimates: estimation.role_estimates || [],
    category_breakdown: estimation.category_breakdown || [],
    total_development_hours: estimation.total_development_hours || 0,
    total_development_cost: estimation.total_development_cost || 0,
    infrastructure_cost_monthly: estimation.infrastructure_cost_monthly || 0,
    third_party_licenses_monthly: estimation.third_party_licenses_monthly || 0,
    contingency_percentage: estimation.contingency_percentage || 0,
    contingency_amount: estimation.contingency_amount || 0,
    grand_total: estimation.grand_total || 0,
    timeline_weeks: estimation.timeline_weeks || 0,
    team_composition: estimation.team_composition || [],
    phases: estimation.phases || [],
    estimation_assumptions: estimation.estimation_assumptions || [],
    web_search_items: web.items || [],
    has_brd: !!data._has_brd,
    has_srs: !!data._has_srs,
    has_quotation: !!data._has_quotation,
    quotation_validation: data.quotation_validation,
    status: data.status || 'Draft',
    converted_project_id: data.converted_project_id || null,
    version: data.version || 0,
  }
}

// Approving is what unlocks project conversion, so every client field is
// required at that point — not just the bare minimum (Company/Contact) that
// ClientDetailsEditor accepts for "Confirm Identity".
const CLIENT_REQUIRED_FOR_APPROVAL: { field: keyof NonNullable<JobResult['client_info']>; label: string }[] = [
  { field: 'company_name', label: 'Company / Organization Name' },
  { field: 'contact_person', label: 'Contact Person' },
  { field: 'email', label: 'Email' },
  { field: 'phone', label: 'Phone' },
  { field: 'gstin', label: 'GSTIN / Tax ID' },
  { field: 'billing_address', label: 'Billing Address' },
]

function missingClientFields(clientInfo: JobResult['client_info']): string[] {
  if (!clientInfo || clientInfo.status !== 'CONFIRMED') {
    return CLIENT_REQUIRED_FOR_APPROVAL.map((f) => f.label)
  }
  return CLIENT_REQUIRED_FOR_APPROVAL.filter((f) => !String(clientInfo[f.field] || '').trim()).map((f) => f.label)
}

export default function EstimationDetail() {
  const { baseName } = useParams<{ baseName: string }>()
  const [result, setResult] = useState<JobResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isConverting, setIsConverting] = useState(false)
  const navigate = useNavigate()

  const handleStatusChange = async (newStatus: string) => {
    if (!baseName || !result) return
    if (newStatus === 'Approved') {
      const missing = missingClientFields(result.client_info)
      if (missing.length > 0) {
        toast.error(`Complete the client's ${missing.join(', ')} before approving this estimation.`, { duration: 6000 })
        document.getElementById('client-details-editor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        return
      }
    }
    try {
      const res = await patchEstimation(baseName, { status: newStatus, version: result.version || 0 })
      setResult(prev => prev ? { ...prev, status: newStatus, version: res.version } : prev)
    } catch (e: any) {
      toast.error(e.message, { duration: 6000 })
      setError(e.message)
    }
  }

  const handleConvert = async () => {
    if (!baseName || !result) return
    const missing = missingClientFields(result.client_info)
    if (missing.length > 0) {
      toast.error(`Complete the client's ${missing.join(', ')} before converting this estimation to a project.`, { duration: 6000 })
      document.getElementById('client-details-editor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    setIsConverting(true)
    try {
      const res = await convertEstimationToProject(baseName)
      navigate(`/invoice/projects/${res.project_id}`)
    } catch (e: any) {
      toast.error(e.message, { duration: 6000 })
      setError(e.message)
      setIsConverting(false)
    }
  }

  useEffect(() => {
    if (!baseName) return
    getEstimationData(baseName)
      .then((data) => setResult(toJobResult(data)))
      .catch((e) => setError(e.message))
  }, [baseName])

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar showBack title={result?.client_name || 'Estimation'} subtitle={result?.project_name}>
        {result && (
          <>
            {result.status === 'Approved' && !result.converted_project_id && (
              <button
                onClick={handleConvert}
                disabled={isConverting}
                title={result.client_info?.status !== 'CONFIRMED' ? 'Client details must be confirmed first' : undefined}
                className="px-4 py-2 bg-brand-600 text-white rounded-full text-sm font-semibold hover:bg-brand-700 transition-colors disabled:opacity-50"
              >
                {isConverting ? 'Converting...' : 'Convert to Project'}
              </button>
            )}
            {result.converted_project_id && (
              <button
                onClick={() => navigate(`/invoice/projects/${result.converted_project_id}`)}
                className="px-4 py-2 bg-slate-100 text-slate-700 border border-slate-200 rounded-full text-sm font-semibold hover:bg-slate-200 transition-colors"
              >
                View Project
              </button>
            )}
            {result.converted_project_id ? (
              <div className="px-3 py-1.5 bg-slate-100 border border-slate-200 text-slate-700 rounded-full text-sm font-medium">
                Status: Converted
              </div>
            ) : (
              <select
                value={result.status || 'Draft'}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="px-3 py-1.5 bg-white border border-slate-200 text-slate-700 rounded-full text-sm font-medium focus:ring-2 focus:ring-brand-300 focus:border-brand-400 outline-none cursor-pointer"
              >
                <option value="Draft">Draft</option>
                <option value="Sent">Sent</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
              </select>
            )}
          </>
        )}
      </Topbar>
      <div className="p-4 sm:p-8">
        {error && <Card className="text-sm text-coral-600 bg-coral-50">{error}</Card>}
        {!result && !error && <LoadingState />}
        {result && baseName && !result.converted_project_id && (
          <div id="client-details-editor">
            <ClientDetailsEditor
              baseName={baseName}
              clientInfo={result.client_info}
              onSaved={(newInfo) => setResult(prev => prev ? { ...prev, client_info: newInfo } : prev)}
            />
          </div>
        )}
        {result && baseName && <EstimationResult result={result} docSource="base" docId={baseName} baseName={baseName} />}
      </div>
    </div>
  )
}
