import { useEffect, useRef, useState } from 'react'
import { matchBillingClassifications } from '../api/client'
import type { BillingClassificationMatch } from '../api/client'

// Below this score, no candidate is considered a confident auto-match —
// mirrors MIN_AUTO_MATCH_SCORE in backend/app/services/invoice_service.py so
// the UI doesn't silently accept a selection the server would reject anyway.
const MIN_CONFIDENT_SCORE = 2

export default function ClassificationPicker({
  description,
  value,
  onChange,
  noSource = false,
}: {
  description: string
  value: { id: string; hsn_sac_code: string; description: string } | null
  onChange: (choice: { id: string; hsn_sac_code: string; description: string } | null) => void
  /** True for CUSTOM line items, which have no milestone/component to inherit
   *  a classification from — auto-match runs from the description alone. */
  noSource?: boolean
}) {
  const [matches, setMatches] = useState<BillingClassificationMatch[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const debounceRef = useRef<number>()
  const lastAutoDescription = useRef<string>('')
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [open])

  useEffect(() => {
    if (!description || description.trim().length < 3) {
      setMatches([])
      return
    }
    window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(async () => {
      setLoading(true)
      try {
        const results = await matchBillingClassifications(description, 5)
        setMatches(results)
        // Auto-select the top confident match only the first time this
        // description produces results, and only if nothing's been chosen
        // yet — never silently override a choice the user already made.
        if (!value && results.length > 0 && results[0].score >= MIN_CONFIDENT_SCORE && lastAutoDescription.current !== description) {
          lastAutoDescription.current = description
          onChange({ id: results[0].id, hsn_sac_code: results[0].hsn_sac_code, description: results[0].description })
        }
      } catch {
        setMatches([])
      } finally {
        setLoading(false)
      }
    }, 400)
    return () => window.clearTimeout(debounceRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [description])

  return (
    <div className="relative" ref={containerRef} onMouseLeave={() => setOpen(false)}>
      <label className="block text-xs font-medium text-slate-500 mb-1">Billing Classification (HSN/SAC)</label>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full text-left border rounded p-2 text-sm flex items-center justify-between gap-2 ${
          value ? 'border-slate-200 bg-white' : 'border-slate-200 bg-slate-50'
        }`}
      >
        {value ? (
          <span className="truncate">
            <span className="font-medium text-slate-700">{value.hsn_sac_code}</span>
            <span className="text-slate-400"> · {value.description}</span>
          </span>
        ) : (
          <span className="text-slate-500">
            {loading ? 'Searching…' : noSource ? 'Auto-matched from description (click to override)' : 'Will inherit from source (click to override)'}
          </span>
        )}
        <span className="text-slate-400 text-xs shrink-0">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {matches.length === 0 && (
            <div className="p-3 text-xs text-slate-400">
              {description.trim().length < 3
                ? 'Type a longer description to search the billing classification catalog.'
                : loading
                ? 'Searching…'
                : 'No candidates found — try a different description.'}
            </div>
          )}
          {matches.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => {
                onChange({ id: m.id, hsn_sac_code: m.hsn_sac_code, description: m.description })
                setOpen(false)
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-brand-50 flex items-center justify-between gap-2 ${
                value?.id === m.id ? 'bg-brand-50' : ''
              }`}
            >
              <span className="min-w-0">
                <span className="font-medium text-slate-700">{m.hsn_sac_code}</span>
                <span className="text-slate-400"> · {m.description}</span>
                <span className="block text-[10px] text-slate-400">{m.category} · GST {m.gst_rate}%</span>
              </span>
              {m.score < MIN_CONFIDENT_SCORE && (
                <span className="text-[10px] text-amber-600 shrink-0">low confidence</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
