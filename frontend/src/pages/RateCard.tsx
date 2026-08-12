import { useEffect, useState } from 'react'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { getRateCard, updateRateCard } from '../api/client'
import type { RateCard as RateCardType } from '../api/types'

export default function RateCardPage() {
  const [rates, setRates] = useState<RateCardType | null>(null)
  const [draft, setDraft] = useState<RateCardType | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [newRoleLabel, setNewRoleLabel] = useState('')
  const [newRoleRate, setNewRoleRate] = useState(0)
  const [addError, setAddError] = useState<string | null>(null)

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

  function handleAddRole() {
    if (!draft) return
    const label = newRoleLabel.trim()
    if (!label) {
      setAddError('Role name cannot be empty')
      return
    }
    const roleKey = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
    if (draft[roleKey]) {
      setAddError('A role with a similar name already exists')
      return
    }
    setDraft({ ...draft, [roleKey]: { rate_per_hour: newRoleRate, label, is_custom: true } })
    setNewRoleLabel('')
    setNewRoleRate(0)
    setAddError(null)
    setSaved(false)
  }

  function handleRemoveRole(key: string) {
    if (!draft) return
    const newDraft = { ...draft }
    delete newDraft[key]
    setDraft(newDraft)
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
      <Topbar showBack title="Rate Card" subtitle="Hourly rates used by the estimation agent for cost calculations." />
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
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-slate-700">{r.label}</span>
                    {r.is_custom && <span className="text-[10px] text-brand-600 bg-brand-50 px-2 py-0.5 rounded w-fit mt-1">Custom</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400 text-sm">₹</span>
                      <input
                        type="number"
                        min={0}
                        max={9999999}
                        step={100}
                        value={r.rate_per_hour}
                        onChange={(e) => updateRate(key, Math.min(9999999, Math.max(0, Number(e.target.value))))}
                        className="w-28 text-right border border-slate-200 rounded-full px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                      />
                      <span className="text-slate-400 text-xs">/hr</span>
                    </div>
                    {r.is_custom ? (
                      <button onClick={() => handleRemoveRole(key)} className="text-slate-300 hover:text-coral-500 text-lg w-6 flex justify-center pb-1">×</button>
                    ) : (
                      <div className="w-6" /> // spacer
                    )}
                  </div>
                </li>
              ))}
              
              <li className="flex flex-col gap-2 pt-6 mt-2 border-t border-slate-100">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Add New Role</span>
                <div className="flex items-center gap-3">
                  <input
                    value={newRoleLabel}
                    onChange={(e) => setNewRoleLabel(e.target.value)}
                    placeholder="e.g. Data Scientist"
                    className="flex-1 border border-slate-200 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                  />
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-slate-400 text-sm">₹</span>
                    <input
                      type="number"
                      min={0}
                      step={100}
                      value={newRoleRate || ''}
                      onChange={(e) => setNewRoleRate(Number(e.target.value))}
                      placeholder="8000"
                      className="w-28 text-right border border-slate-200 rounded-full px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                    />
                    <span className="text-slate-400 text-xs">/hr</span>
                  </div>
                  <button
                    onClick={handleAddRole}
                    className="shrink-0 text-sm font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 px-5 py-2 rounded-full transition-colors"
                  >
                    Add
                  </button>
                </div>
                {addError && <span className="text-xs text-coral-600">{addError}</span>}
              </li>
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
