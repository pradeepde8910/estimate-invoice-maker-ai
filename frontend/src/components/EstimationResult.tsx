import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Card from './Card'
import HeroStat from './HeroStat'
import StatCard from './StatCard'
import DonutChart from './DonutChart'
import { downloadEstimationExcel, downloadEstimationTimelineExcel } from '../api/client'
import type { JobResult, Phase, RequirementEstimate, TaskEstimate } from '../api/types'

export const inr = (n: number) => '₹' + Math.round(n || 0).toLocaleString('en-IN')

export const compactInr = (n: number) => {
  const value = n || 0;
  const format = (v: number) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(v);
  if (value < 1000) return `₹${format(value)}`;
  if (value < 100000) return `₹${format(value / 1000)} K`;
  if (value < 10000000) return `₹${format(value / 100000)} L`;
  return `₹${format(value / 10000000)} Cr`;
};

// ── Scope badge ──────────────────────────────────────────────────────────────
function ScopeBadge({ status }: { status: string }) {
  const isOut = status === 'OUT_OF_SCOPE'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider shadow-sm ${
      isOut
        ? 'bg-slate-50 text-slate-500 border border-slate-200/60'
        : 'bg-teal-50/80 text-teal-700 border border-teal-100/60'
    }`}>
      {isOut ? '✕ Out of Scope' : '✓ In Scope'}
    </span>
  )
}

// ── Implementation tasks expandable row ──────────────────────────────────────
function RequirementRow({ req }: { req: RequirementEstimate }) {
  const [open, setOpen] = useState(false)
  const isOut = req.scope_status === 'OUT_OF_SCOPE'
  const hasTasks = req.implementation_tasks && req.implementation_tasks.length > 0

  return (
    <>
      <tr
        className={`border-b border-slate-50 transition-colors ${hasTasks && !isOut ? 'cursor-pointer hover:bg-slate-50' : ''}`}
        onClick={() => hasTasks && !isOut && setOpen(o => !o)}
      >
        {/* Title + scope */}
        <td className="py-2.5 pr-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm ${isOut ? 'line-through text-slate-400' : 'text-slate-700'}`}>
              {req.title}
            </span>
            <ScopeBadge status={req.scope_status || 'IN_SCOPE'} />
          </div>
          {isOut && req.adjustment_reason && req.adjustment_reason !== 'no change' && (
            <p className="text-xs text-slate-400 mt-0.5 italic">{req.adjustment_reason}</p>
          )}
        </td>
        {/* Category */}
        <td className="py-2.5 text-xs text-slate-400 w-28 hidden md:table-cell">{req.category || '—'}</td>
        {/* Tasks toggle */}
        <td className="py-2.5 text-xs text-slate-400 w-20 text-center hidden sm:table-cell">
          {!isOut && hasTasks && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-white border border-slate-200/60 shadow-sm text-slate-500 text-[10px] transition-colors">
              {req.implementation_tasks.length} {open ? '▲' : '▼'}
            </span>
          )}
        </td>
        {/* Hours */}
        <td className="py-2.5 text-right text-slate-500 text-sm w-16">{isOut ? '—' : `${req.hours}h`}</td>
        {/* Cost */}
        <td className="py-2.5 text-right font-semibold text-sm w-28 text-slate-800">
          {isOut ? <span className="text-slate-400 font-normal">Excluded</span> : inr(req.cost)}
        </td>
      </tr>

      {/* Tasks breakdown */}
      {open && hasTasks && (
        <tr className="bg-slate-50/60">
          <td colSpan={5} className="px-4 pb-3 pt-1">
            <div className="border border-slate-100 rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-100 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="px-3 py-2 text-left">Implementation Task</th>
                    <th className="px-3 py-2 text-left">Role</th>
                    <th className="px-3 py-2 text-right">Hours</th>
                    <th className="px-3 py-2 text-right">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 bg-white">
                  {req.implementation_tasks.map((t: TaskEstimate, i: number) => (
                    <tr key={i} className="hover:bg-slate-50/50">
                      <td className="px-3 py-2 text-slate-700">{t.task}</td>
                      <td className="px-3 py-2 text-slate-500">{t.role_label || t.role_key}</td>
                      <td className="px-3 py-2 text-right text-slate-500">{t.hours}h</td>
                      <td className="px-3 py-2 text-right font-medium text-slate-700">{inr(t.cost)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-slate-50 font-semibold text-xs text-slate-600">
                    <td className="px-3 py-2" colSpan={2}>Requirement Total</td>
                    <td className="px-3 py-2 text-right">{req.hours}h</td>
                    <td className="px-3 py-2 text-right">{inr(req.cost)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Quotation health report panel ────────────────────────────────────────────
function QuotationHealthPanel({ validation }: { validation: JobResult['quotation_validation'] }) {
  if (!validation) return null

  const { is_valid, error_count, warning_count, errors, warnings } = validation
  const hasIssues = error_count > 0 || warning_count > 0

  if (!hasIssues) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-2xl bg-teal-50/40 border border-teal-100/50">
        <span className="text-2xl">✅</span>
        <div>
          <p className="text-sm font-medium text-teal-800">Quotation Validated</p>
          <p className="text-xs text-teal-600/80 mt-0.5">All 13 checks passed. No financial inconsistencies detected.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`rounded-2xl border p-4 ${is_valid ? 'bg-amber-50/40 border-amber-100/50' : 'bg-rose-50/40 border-rose-100/50'}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">{is_valid ? '⚠️' : '❌'}</span>
        <p className={`text-sm font-medium ${is_valid ? 'text-amber-800' : 'text-rose-800'}`}>
          Quotation Health Report
        </p>
        <div className="ml-auto flex gap-2">
          {error_count > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white border border-rose-100 text-rose-600 shadow-sm">
              {error_count} Error{error_count !== 1 ? 's' : ''}
            </span>
          )}
          {warning_count > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white border border-amber-100 text-amber-600 shadow-sm">
              {warning_count} Warning{warning_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {errors.length > 0 && (
        <div className="space-y-1 mb-2">
          {errors.map((e, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-rose-700 bg-white/60 rounded-xl px-3 py-2 border border-rose-50">
              <span className="mt-0.5 shrink-0 text-[10px]">✕</span>
              <span>{e.replace(/^Check \d+ FAIL — /, '')}</span>
            </div>
          ))}
        </div>
      )}

      {warnings.length > 0 && (
        <div className="space-y-1">
          {warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-700 bg-white/60 rounded-xl px-3 py-2 border border-amber-50">
              <span className="mt-0.5 shrink-0 text-[10px]">⚠</span>
              <span>{w.replace(/^Check \d+ WARN — /, '')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Project timeline / phases ─────────────────────────────────────────────────
function ProjectTimeline({ phases, timelineWeeks, baseName }: { phases: Phase[]; timelineWeeks: number; baseName?: string | null }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleDownloadTimeline() {
    if (!baseName) return
    setDownloading(true)
    setError(null)
    try {
      await downloadEstimationTimelineExcel(baseName)
    } catch (e: any) {
      setError(e.message || 'Failed to download timeline')
    } finally {
      setDownloading(false)
    }
  }

  let elapsed = 0;
  const scheduleUnits = phases.map(phase => {
    const startWeek = elapsed;
    elapsed += phase.duration_weeks || 0;
    return {
      name: phase.name,
      description: phase.description,
      startWeek,
      endWeek: elapsed,
      durationWeeks: phase.duration_weeks,
      type: 'PHASE'
    };
  });

  const totalWeeks = Math.max(timelineWeeks, elapsed, 1);
  const weekMarkers = Array.from({ length: totalWeeks }, (_, i) => i + 1);

  return (
    <div className="space-y-6">
      <Card title="Project Timeline & Schedule">
        <div className="flex justify-between items-end mb-6">
          <div>
            <p className="text-sm text-slate-500">Estimated delivery · {scheduleUnits.length} schedule units</p>
          </div>
          <div className="text-right flex items-center gap-3">
            <span className="text-sm font-bold text-slate-800">{timelineWeeks} Weeks Total</span>
            {baseName && (
              <button
                onClick={handleDownloadTimeline}
                disabled={downloading}
                title="Download this timeline as an Excel workbook with a Gantt chart"
                className="text-xs font-medium bg-slate-50 hover:bg-indigo-50 hover:text-indigo-700 text-slate-600 px-3 py-1.5 rounded-full border border-slate-100/50 hover:border-indigo-100 transition-all disabled:opacity-50"
              >
                {downloading ? 'Preparing…' : '⬇ Download Timeline (Excel)'}
              </button>
            )}
          </div>
        </div>
        {error && <div className="text-xs text-coral-600 mb-3">{error}</div>}

        <div className="relative overflow-x-auto pb-6">
          <div className="min-w-[600px] relative">
            
            {/* Grid Lines Background */}
            <div className="absolute top-6 bottom-0 left-32 right-0 flex z-0 pointer-events-none">
              {weekMarkers.map(w => (
                <div key={w} className="flex-1 flex justify-center">
                  <div className="w-px h-full bg-slate-100" />
                </div>
              ))}
            </div>

            {/* Week Headers */}
            <div className="flex mb-4 pl-32 relative z-10">
              {weekMarkers.map(w => (
                <div key={w} className="flex-1 text-center">
                  <div className="text-[10px] font-semibold text-slate-400 mb-2">W{w}</div>
                </div>
              ))}
            </div>

            {/* Timeline Bars */}
            <div className="space-y-8 relative z-10 mt-6 pb-4">
              {scheduleUnits.map((unit, i) => {
                const widthPct = (unit.durationWeeks / totalWeeks) * 100;
                const leftPct = (unit.startWeek / totalWeeks) * 100;
                
                const barColors = [
                  'bg-indigo-400 group-hover:bg-indigo-500 shadow-indigo-200',
                  'bg-teal-400 group-hover:bg-teal-500 shadow-teal-200',
                  'bg-blue-400 group-hover:bg-blue-500 shadow-blue-200',
                  'bg-violet-400 group-hover:bg-violet-500 shadow-violet-200',
                  'bg-rose-400 group-hover:bg-rose-500 shadow-rose-200'
                ];
                const colorClass = barColors[i % barColors.length];
                
                return (
                  <div key={i} className="flex relative items-start group">
                    <div className="w-32 shrink-0 pr-4 pt-1 z-20 bg-white">
                      <h4 className="font-medium text-slate-800 text-sm truncate" title={unit.name}>{unit.name}</h4>
                    </div>
                    <div className="flex-1 relative h-8">
                       <div 
                         className={`absolute top-0 h-6 ${colorClass} rounded-md opacity-90 group-hover:opacity-100 shadow-sm group-hover:shadow-md group-hover:scale-y-[1.05] transition-all duration-300 cursor-pointer`}
                         style={{ width: `${widthPct}%`, left: `${leftPct}%` }}
                       />
                       <div 
                         className="absolute top-7 text-[10px] font-medium text-slate-400 whitespace-nowrap transition-colors group-hover:text-slate-700"
                         style={{ left: `${leftPct}%` }}
                       >
                         Week {unit.startWeek + 1} – {unit.endWeek} · {unit.durationWeeks} weeks
                       </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </Card>
      
      {/* Unit Details Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {scheduleUnits.map((unit, i) => {
           const badgeColors = [
             'bg-indigo-50 text-indigo-600 border-indigo-100',
             'bg-teal-50 text-teal-600 border-teal-100',
             'bg-blue-50 text-blue-600 border-blue-100',
             'bg-violet-50 text-violet-600 border-violet-100',
             'bg-rose-50 text-rose-600 border-rose-100'
           ];
           const badgeClass = badgeColors[i % badgeColors.length];

           return (
           <div key={i} className="p-5 bg-slate-50/50 border border-slate-100/50 rounded-2xl hover:bg-slate-50 hover:border-slate-200/60 transition-all duration-300 group">
             <div className="flex justify-between items-start mb-3">
               <h4 className="font-medium text-slate-800 flex items-center gap-2">
                 <span className="text-xs font-semibold text-slate-300 group-hover:text-slate-400 transition-colors">{String(i + 1).padStart(2, '0')}</span>
                 <span className="line-clamp-1" title={unit.name}>{unit.name}</span>
               </h4>
               <span className={`text-[10px] font-medium ${badgeClass} border px-2.5 py-1 rounded-full whitespace-nowrap shrink-0`}>{unit.durationWeeks} weeks</span>
             </div>
             <p className="text-xs text-slate-500 leading-relaxed mb-4 line-clamp-2" title={unit.description}>{unit.description || 'No description provided.'}</p>
             <div className="text-[10px] font-medium text-slate-400 flex items-center gap-2 mt-auto">
               <span>Week {unit.startWeek + 1}</span>
               <span className="text-slate-300 font-light">—</span>
               <span>Week {unit.endWeek}</span>
             </div>
           </div>
        )})}
      </div>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
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
  const [downloadingExcel, setDownloadingExcel] = useState(false)
  const [excelError, setExcelError] = useState<string | null>(null)
  const resourceCount = result.role_estimates?.length ?? 0
  const docPath = (type: string) =>
    baseName
      ? `/estimation/document/base/${baseName}/${type}`
      : docSource === 'job'
      ? `/estimation/document/${docId}/${type}`
      : `/estimation/document/base/${docId}/${type}`

  // Count in-scope vs out-of-scope requirements across all units
  const allReqs = (result.unit_estimates ?? []).flatMap(u => u.requirement_estimates ?? [])
  const inScopeCount = allReqs.filter(r => r.scope_status !== 'OUT_OF_SCOPE').length
  const outScopeCount = allReqs.filter(r => r.scope_status === 'OUT_OF_SCOPE').length

  async function handleDownloadExcel() {
    if (!baseName) return
    setDownloadingExcel(true)
    setExcelError(null)
    try {
      await downloadEstimationExcel(baseName)
    } catch (e: any) {
      setExcelError(e.message || 'Failed to download workbook')
    } finally {
      setDownloadingExcel(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Hero stats ── */}
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

      {/* ── Health report + charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col gap-4">
          {/* Health panel */}
          {result.quotation_validation && (
            <QuotationHealthPanel validation={result.quotation_validation} />
          )}

          {/* Cost breakdown charts */}
          <Card title="Cost Breakdown">
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
        </div>

        {/* Documents + scope summary */}
        <div className="flex flex-col gap-4">
          <Card title="Documents & Next Step">
            <div className="grid grid-cols-2 gap-2">
              <DocAction label="BRD" ready={result.has_brd} onClick={() => navigate(docPath('brd'))} />
              <DocAction label="SRS" ready={result.has_srs} onClick={() => navigate(docPath('srs'))} />
              <DocAction label="Quotation" ready={result.has_quotation} onClick={() => navigate(docPath('quotation'))} />
            </div>
            {baseName && (
              <div className="mt-3 pt-3 border-t border-slate-100">
                <button
                  onClick={handleDownloadExcel}
                  disabled={downloadingExcel}
                  title="Complete estimation workbook — overview, timeline, cost breakdowns, requirements, task-level detail, team, infrastructure/license costs, risks & assumptions, with charts"
                  className="w-full px-3 py-3 rounded-2xl text-sm font-medium bg-brand-50 text-brand-700 hover:bg-brand-100 transition-colors disabled:opacity-50"
                >
                  {downloadingExcel ? 'Preparing…' : '⬇ Download Complete Estimation (Excel)'}
                </button>
                {excelError && <p className="text-xs text-coral-600 mt-2">{excelError}</p>}
              </div>
            )}
          </Card>

          {/* Scope summary */}
          {(inScopeCount > 0 || outScopeCount > 0) && (
            <Card title="Scope Summary">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">In Scope</span>
                  <span className="text-sm font-bold text-emerald-600">{inScopeCount} requirements</span>
                </div>
                {outScopeCount > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Out of Scope</span>
                    <span className="text-sm font-bold text-red-500">{outScopeCount} requirements</span>
                  </div>
                )}
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div
                    className="bg-emerald-400 h-2 rounded-full transition-all"
                    style={{ width: `${(inScopeCount / (inScopeCount + outScopeCount)) * 100}%` }}
                  />
                </div>
              </div>
            </Card>
          )}

          {/* Estimation assumptions */}
          {result.estimation_assumptions && result.estimation_assumptions.length > 0 && (
            <Card title="Estimation Assumptions">
              <ul className="space-y-2">
                {result.estimation_assumptions.map((a, i) => (
                  <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                    <span className="text-slate-400 shrink-0 mt-0.5">•</span>
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>

      {/* ── Delivery structure with task traceability ── */}
      {result.unit_estimates && result.unit_estimates.length > 0 && (
        <Card title="Delivery Structure & Requirements" className="w-full">
          {result.project_structure && (
            <div className="mb-6 p-5 bg-indigo-50/30 rounded-2xl border border-indigo-100/50 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-800">
                  Detected Structure: <span className="font-semibold text-indigo-600 capitalize">{result.project_structure.structure_type.replace('_', ' ')}</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">Based on '{result.project_structure.source_term || 'flat content'}' terminology.</p>
              </div>
              <p className="text-[10px] font-medium text-slate-500 hidden md:block bg-white px-3 py-1.5 rounded-full shadow-sm border border-slate-100">Click any in-scope requirement to expand its implementation tasks</p>
            </div>
          )}

          <div className="space-y-4">
            {result.unit_estimates.map(unit => {
              const unitInScope = (unit.requirement_estimates ?? []).filter(r => r.scope_status !== 'OUT_OF_SCOPE').length
              const unitOutScope = (unit.requirement_estimates ?? []).filter(r => r.scope_status === 'OUT_OF_SCOPE').length
              return (
                <div key={unit.unit_id} className="border border-slate-100 rounded-xl overflow-hidden">
                  {/* Unit header */}
                  <div className="bg-slate-50 px-4 py-3 flex justify-between items-center border-b border-slate-100">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-semibold text-slate-800">{unit.label}</h4>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-white text-slate-500 border border-slate-200">
                        {unit.semantic_type}
                      </span>
                      {unit.billing?.is_billing_unit && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wider bg-white text-indigo-600 border border-indigo-100/60 shadow-sm">
                          💰 Billing Unit
                        </span>
                      )}
                      <span className="text-xs text-slate-400">{unitInScope} in scope{unitOutScope > 0 ? ` · ${unitOutScope} excluded` : ''}</span>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className="font-bold text-slate-900">{inr(unit.estimate.cost)}</p>
                      <p className="text-xs font-medium text-slate-500">{unit.estimate.hours}h</p>
                    </div>
                  </div>

                  {/* Requirements table */}
                  {unit.requirement_estimates && unit.requirement_estimates.length > 0 && (
                    <div className="p-4 bg-white overflow-x-auto">
                      <table className="w-full text-sm min-w-[520px]">
                        <thead>
                          <tr className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold border-b border-slate-100">
                            <th className="pb-2 text-left">Requirement</th>
                            <th className="pb-2 text-left hidden md:table-cell">Category</th>
                            <th className="pb-2 text-center hidden sm:table-cell">Tasks</th>
                            <th className="pb-2 text-right">Hours</th>
                            <th className="pb-2 text-right">Cost</th>
                          </tr>
                        </thead>
                        <tbody>
                          {unit.requirement_estimates.map(req => (
                            <RequirementRow key={req.requirement_id} req={req} />
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="border-t border-slate-200 font-semibold text-slate-700">
                            <td className="pt-2" colSpan={3}>Unit Total</td>
                            <td className="pt-2 text-right">{unit.estimate.hours}h</td>
                            <td className="pt-2 text-right">{inr(unit.estimate.cost)}</td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* ── Project timeline / phases ── */}
      {result.phases && result.phases.length > 0 && (
        <ProjectTimeline phases={result.phases} timelineWeeks={result.timeline_weeks} baseName={baseName} />
      )}
    </div>
  )
}

function DocAction({ label, ready, onClick }: { label: string; ready: boolean; onClick: () => void }) {
  return (
    <button
      disabled={!ready}
      onClick={onClick}
      className={`px-3 py-3 rounded-2xl text-sm font-medium transition-all duration-300 ${
        ready ? 'bg-slate-50 text-slate-700 hover:bg-indigo-50/80 hover:text-indigo-700 hover:shadow-sm border border-slate-100/50 hover:border-indigo-100' : 'bg-slate-50/50 text-slate-300 cursor-not-allowed border border-transparent'
      }`}
    >
      {label}
    </button>
  )
}
