import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import EstimationResult from '../components/EstimationResult'
import { getEstimationData } from '../api/client'
import type { JobResult } from '../api/types'

function toJobResult(data: any): JobResult {
  const analysis = data.analysis || {}
  const estimation = data.cost_estimation || {}
  const web = data.web_search_data || {}
  return {
    client_name: data.client_name || analysis.client_name || 'Unspecified Client',
    project_name: data.project_name || analysis.project_name || '',
    project_type: analysis.project_type || '',
    project_description: analysis.project_description || '',
    tech_stack_suggested: analysis.tech_stack_suggested || [],
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
    web_search_items: web.items || [],
    has_brd: !!data._has_brd,
    has_srs: !!data._has_srs,
    has_quotation: !!data._has_quotation,
  }
}

export default function EstimationDetail() {
  const { baseName } = useParams<{ baseName: string }>()
  const [result, setResult] = useState<JobResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!baseName) return
    getEstimationData(baseName)
      .then((data) => setResult(toJobResult(data)))
      .catch((e) => setError(e.message))
  }, [baseName])

  return (
    <div className="flex-1">
      <Topbar showBack title={result?.client_name || 'Estimation'} subtitle={result?.project_name} />
      <div className="p-8">
        {error && <Card className="text-sm text-coral-600 bg-coral-50">{error}</Card>}
        {!result && !error && <p className="text-sm text-slate-400">Loading…</p>}
        {result && baseName && <EstimationResult result={result} docSource="base" docId={baseName} baseName={baseName} />}
      </div>
    </div>
  )
}
