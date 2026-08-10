import { useEffect, useState } from 'react'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import BackLink from '../components/BackLink'
import { getRateCard, updateRateCard } from '../api/client'
import type { RateCard as RateCardType } from '../api/types'

export default function RateCardPage() {
  const [rates, setRates] = useState<RateCardType | null>(null)
  const [draft, setDraft] = useState<RateCardType | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getRateCard()
      .then((r) => {
        setRates(r.rates)
        setDraft(structuredClone(r.rates))
      })
      .catch((e) => setError(e.message))
  }, [])

  const dirty = rates && draft && JSON.stringify(rates) !== JSON.stringify(draft)

  function updateRate(key: string, value: number) {
    if (!draft) return
    setDraft({ ...draft, [key]: { ...draft[key], rate_per_hour: value } })
    setSaved(false)
  }

  async function save() {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const r = await updateRateCard(draft)
      setRates(r.rates)
      setDraft(structuredClone(r.rates))
      setSaved(true)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex-1">
      <BackLink />
      <Topbar title="Rate Card" subtitle="Hourly rates used by the estimation agent for cost calculations." />
      <div className="p-6 max-w-3xl">
        <Card
          title="Developer Rates (INR / hour)"
          action={
            <div className="flex items-center gap-3">
              {saved && <span className="text-xs text-brand-600 font-medium">Saved ✓</span>}
              {dirty && (
                <button
                  disabled={saving}
                  onClick={() => {
                    if (rates) setDraft(structuredClone(rates))
                    setSaved(false)
                    setError(null)
                  }}
                  className="text-sm font-medium text-slate-500 hover:text-slate-800 disabled:text-slate-300"
                >
                  Discard
                </button>
              )}
              <button
                disabled={!dirty || saving}
                onClick={save}
                className="text-sm font-medium bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 disabled:text-slate-400 text-white px-5 py-2 rounded-full"
              >
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          }
        >
          {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-3 py-2 mb-4">{error}</div>}
          {!draft ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {Object.entries(draft).map(([key, r]) => (
                <li key={key} className="flex items-center justify-between py-3">
                  <span className="text-sm text-slate-700">{r.label}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400 text-sm">₹</span>
                    <input
                      type="number"
                      min={0}
                      step={100}
                      value={r.rate_per_hour}
                      onChange={(e) => updateRate(key, Number(e.target.value))}
                      className="w-28 text-right border border-slate-200 rounded-full px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                    />
                    <span className="text-slate-400 text-xs">/hr</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <p className="text-xs text-slate-400 mt-4">
          Changes apply to all future analyses. Existing quotations are not recalculated retroactively.
        </p>
      </div>
    </div>
  )
}
