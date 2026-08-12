import { useNavigate } from 'react-router-dom'
import Card from './Card'
import HeroStat from './HeroStat'
import StatCard from './StatCard'
import DonutChart from './DonutChart'
import type { JobResult } from '../api/types'

export const inr = (n: number) => '₹' + Math.round(n || 0).toLocaleString('en-IN')

export default function EstimationResult({
  result,
  docSource,
  docId,
  baseName,
}: {
  result: JobResult
  docSource: 'job' | 'base'
  docId: string
  baseName?: string | null
}) {
  const navigate = useNavigate()
  const resourceCount = result.role_estimates?.length ?? 0
  // Prefer the base-name route whenever it's available (it always is once a
  // result is shown) so editing/PDF export — which operate on saved files —
  // work regardless of whether we got here from a live job or history.
  const docPath = (type: string) =>
    baseName
      ? `/estimation/document/base/${baseName}/${type}`
      : docSource === 'job'
      ? `/estimation/document/${docId}/${type}`
      : `/estimation/document/base/${docId}/${type}`

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <HeroStat tone="coral" label="Grand Total" value={inr(result.grand_total)} sub="Incl. contingency" />
        <HeroStat tone="mint" label="Timeline" value={`${result.timeline_weeks}`} sub="Weeks" />
        <Card className="flex flex-col justify-center">
          <StatCard label="Effort" value={Math.round(result.total_development_hours)} sub="Person hours" />
        </Card>
        <Card className="flex flex-col justify-center">
          <StatCard label="Resources" value={resourceCount} sub="Roles" />
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Cost Breakdown" className="lg:col-span-2">
          <div className="flex flex-col gap-8">
            <div>
              <div className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-5 text-center">By Role</div>
              <DonutChart
                data={result.role_estimates.map((r) => ({ name: r.role_label, value: r.total_cost }))}
                valueFormatter={inr}
                centerLabel={{ value: inr(result.total_development_cost), label: 'Dev Cost' }}
              />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-600 uppercase tracking-wide mb-5 text-center">By Category</div>
              <DonutChart
                data={result.category_breakdown.map((c) => ({ name: c.category, value: c.total_cost }))}
                valueFormatter={inr}
                centerLabel={{ value: String(result.category_breakdown.length), label: 'Categories' }}
              />
            </div>
          </div>
        </Card>

        <Card title="Documents & Next Step">
          <div className="grid grid-cols-2 gap-2">
            <DocAction label="BRD" ready={result.has_brd} onClick={() => navigate(docPath('brd'))} />
            <DocAction label="SRS" ready={result.has_srs} onClick={() => navigate(docPath('srs'))} />
            <DocAction label="Quotation" ready={result.has_quotation} onClick={() => navigate(docPath('quotation'))} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function DocAction({ label, ready, onClick }: { label: string; ready: boolean; onClick: () => void }) {
  return (
    <button
      disabled={!ready}
      onClick={onClick}
      className={`px-3 py-3 rounded-2xl text-sm font-medium transition-colors ${
        ready ? 'bg-slate-50 text-slate-700 hover:bg-brand-50 hover:text-brand-700' : 'text-slate-300 cursor-not-allowed'
      }`}
    >
      {label}
    </button>
  )
}
