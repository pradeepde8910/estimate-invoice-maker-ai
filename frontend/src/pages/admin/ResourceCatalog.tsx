import { useEffect, useState } from 'react'
import Topbar from '../../components/Topbar'
import Card from '../../components/Card'
import {
  listCapabilities, createCapability, deleteCapability,
  listProviders, createProvider, deleteProvider,
  listTechnologyModels, createTechnologyModel, deleteTechnologyModel,
  addModelFeature, deleteModelFeature,
  addPricingRule, updatePricingRule, deletePricingRule,
} from '../../api/client'

const CATEGORIES = ['ai_service', 'infrastructure', 'external_service', 'software_license']
const PRICING_MODELS = ['FLAT', 'PER_UNIT', 'TIERED', 'SUBSCRIPTION_PLUS_USAGE', 'MINIMUM_COMMITMENT']
const PRICING_SOURCES = ['verified_catalog', 'vendor_docs', 'market_estimate']

function pricingSourceBadge(source: string) {
  const tone =
    source === 'verified_catalog' ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400' :
    source === 'vendor_docs' ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400' :
    'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400'
  const label = source === 'verified_catalog' ? 'Verified' : source === 'vendor_docs' ? 'Vendor Docs' : 'Market Estimate'
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{label}</span>
}

export default function ResourceCatalog() {
  const [capabilities, setCapabilities] = useState<any[]>([])
  const [providers, setProviders] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [newCapability, setNewCapability] = useState({ key: '', name: '', category: 'ai_service', description: '' })
  const [newProvider, setNewProvider] = useState({ key: '', name: '', website: '' })
  const [newModel, setNewModel] = useState({ provider_id: '', capability_id: '', model_key: '', model_name: '', description: '' })

  const [expandedModel, setExpandedModel] = useState<string | null>(null)
  const [newFeature, setNewFeature] = useState({ feature_key: '', feature_value: '' })
  const [newPricing, setNewPricing] = useState<any>({
    pricing_model: 'PER_UNIT', unit_type: '', price: '', currency: 'INR',
    pricing_source: 'market_estimate', source_url: '', last_verified_on: '',
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [groupBy, setGroupBy] = useState<'provider' | 'capability'>('provider')

  function loadAll() {
    setLoading(true)
    Promise.all([listCapabilities(), listProviders(), listTechnologyModels()])
      .then(([caps, provs, mods]) => {
        setCapabilities(caps)
        setProviders(provs)
        setModels(mods)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadAll() }, [])

  async function handleCreateCapability(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createCapability(newCapability)
      setNewCapability({ key: '', name: '', category: 'ai_service', description: '' })
      loadAll()
    } catch (e: any) { setError(e.message) }
  }

  async function handleCreateProvider(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createProvider(newProvider)
      setNewProvider({ key: '', name: '', website: '' })
      loadAll()
    } catch (e: any) { setError(e.message) }
  }

  async function handleCreateModel(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await createTechnologyModel(newModel)
      setNewModel({ provider_id: '', capability_id: '', model_key: '', model_name: '', description: '' })
      loadAll()
    } catch (e: any) { setError(e.message) }
  }

  async function handleAddFeature(modelId: string) {
    if (!newFeature.feature_key || !newFeature.feature_value) return
    try {
      await addModelFeature(modelId, newFeature)
      setNewFeature({ feature_key: '', feature_value: '' })
      loadAll()
    } catch (e: any) { setError(e.message) }
  }

  async function handleAddPricing(modelId: string) {
    if (!newPricing.price) return
    try {
      await addPricingRule(modelId, {
        ...newPricing,
        price: parseFloat(newPricing.price),
        last_verified_on: newPricing.last_verified_on ? new Date(newPricing.last_verified_on).toISOString() : null,
      })
      setNewPricing({ pricing_model: 'PER_UNIT', unit_type: '', price: '', currency: 'INR', pricing_source: 'market_estimate', source_url: '', last_verified_on: '' })
      loadAll()
    } catch (e: any) { setError(e.message) }
  }

  return (
    <div className="flex-1 bg-transparent dark:bg-slate-950 min-h-screen">
      <Topbar
        showBack
        title="Resource & Capability Catalog"
        subtitle="What projects can need (capabilities), who can provide it (vendors/models), and what it costs — kept separate on purpose."
      />

      <div className="p-8 space-y-6 max-w-6xl mx-auto">
        {error && <div className="p-4 bg-coral-50 dark:bg-coral-950/40 text-coral-600 dark:text-coral-400 rounded-2xl">{error}</div>}

        {loading ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Loading…</p>
        ) : (
          <>
            {/* Capabilities */}
            <Card title="Capabilities">
              <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">
                The canonical vocabulary of what a project might need — speech-to-text, object storage, LLM inference, etc.
              </p>
              <form onSubmit={handleCreateCapability} className="grid grid-cols-4 gap-3 mb-4">
                <input required placeholder="key (e.g. speech_to_text)" value={newCapability.key}
                  onChange={(e) => setNewCapability({ ...newCapability, key: e.target.value })}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                <input required placeholder="Display name" value={newCapability.name}
                  onChange={(e) => setNewCapability({ ...newCapability, name: e.target.value })}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                <select value={newCapability.category} onChange={(e) => setNewCapability({ ...newCapability, category: e.target.value })}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100">
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                <button type="submit" className="bg-brand-600 text-white rounded-lg px-3 py-2 text-sm font-medium hover:bg-brand-700">+ Add</button>
              </form>
              <div className="flex flex-wrap gap-2">
                {capabilities.map((c) => (
                  <span key={c.id} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {c.name} <span className="text-slate-400 dark:text-slate-500">· {c.category}</span>
                    <button onClick={() => deleteCapability(c.id).then(loadAll)} className="text-slate-400 hover:text-coral-500">×</button>
                  </span>
                ))}
                {capabilities.length === 0 && <p className="text-sm text-slate-400 dark:text-slate-500">No capabilities yet.</p>}
              </div>
            </Card>

            {/* Providers */}
            <Card title="Providers">
              <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">Vendors — Sarvam, OpenAI, AWS, Twilio, etc.</p>
              <form onSubmit={handleCreateProvider} className="grid grid-cols-4 gap-3 mb-4">
                <input required placeholder="key (e.g. sarvam)" value={newProvider.key}
                  onChange={(e) => setNewProvider({ ...newProvider, key: e.target.value })}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                <input required placeholder="Display name" value={newProvider.name}
                  onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                <input placeholder="Website (optional)" value={newProvider.website}
                  onChange={(e) => setNewProvider({ ...newProvider, website: e.target.value })}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                <button type="submit" className="bg-brand-600 text-white rounded-lg px-3 py-2 text-sm font-medium hover:bg-brand-700">+ Add</button>
              </form>
              <div className="flex flex-wrap gap-2">
                {providers.map((p) => (
                  <span key={p.id} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {p.name}
                    <button onClick={() => deleteProvider(p.id).then(loadAll)} className="text-slate-400 hover:text-coral-500">×</button>
                  </span>
                ))}
                {providers.length === 0 && <p className="text-sm text-slate-400 dark:text-slate-500">No providers yet.</p>}
              </div>
            </Card>

            {/* Models */}
            <Card title="Models & Pricing">
              <p className="text-xs text-slate-400 dark:text-slate-500 mb-4">
                One vendor's specific offering for one capability. Pricing is deliberately never seeded automatically —
                add it here once you've confirmed the real number against the vendor's official pricing page.
              </p>
              
              <div className="bg-slate-50 dark:bg-slate-900 rounded-xl p-4 mb-6 border border-slate-100 dark:border-slate-800">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Add New Model</h4>
                <form onSubmit={handleCreateModel} className="grid grid-cols-5 gap-3">
                  <select required value={newModel.provider_id} onChange={(e) => setNewModel({ ...newModel, provider_id: e.target.value })}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100">
                    <option value="">Provider…</option>
                    {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                  <select required value={newModel.capability_id} onChange={(e) => setNewModel({ ...newModel, capability_id: e.target.value })}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100">
                    <option value="">Capability…</option>
                    {capabilities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <input required placeholder="model_key" value={newModel.model_key}
                    onChange={(e) => setNewModel({ ...newModel, model_key: e.target.value })}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                  <input required placeholder="Display name" value={newModel.model_name}
                    onChange={(e) => setNewModel({ ...newModel, model_name: e.target.value })}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100" />
                  <button type="submit" className="bg-brand-600 text-white rounded-lg px-3 py-2 text-sm font-medium hover:bg-brand-700">+ Add</button>
                </form>
              </div>

              <div className="flex items-center justify-between mb-4 mt-8">
                <input
                  type="text"
                  placeholder="Search models..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 w-64"
                />
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-slate-500">Group by:</span>
                  <select 
                    value={groupBy} 
                    onChange={(e) => setGroupBy(e.target.value as any)}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 text-sm bg-white dark:bg-slate-800"
                  >
                    <option value="provider">Provider</option>
                    <option value="capability">Capability</option>
                  </select>
                </div>
              </div>

              <div className="space-y-8">
                {(() => {
                  const safeSearch = searchQuery.toLowerCase();
                  const filtered = models.filter(m => 
                    (m.model_name || '').toLowerCase().includes(safeSearch) || 
                    (m.model_key || '').toLowerCase().includes(safeSearch) ||
                    (m.provider?.name || '').toLowerCase().includes(safeSearch) ||
                    (m.capability?.name || '').toLowerCase().includes(safeSearch)
                  );
                  
                  const grouped = filtered.reduce<Record<string, any[]>>((acc, m) => {
                    const key = groupBy === 'provider'
                      ? (m.provider?.name || 'Unknown Provider')
                      : (m.capability?.name || 'Unknown Capability');
                    if (!acc[key]) acc[key] = [];
                    acc[key].push(m);
                    return acc;
                  }, {});

                  if (Object.keys(grouped).length === 0) {
                    return <p className="text-sm text-slate-400 dark:text-slate-500 py-4 text-center">No models found.</p>;
                  }

                  return Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([groupName, groupModels]) => (
                    <div key={groupName} className="space-y-2">
                      <h3 className="font-semibold text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-700 pb-1 mb-2 mt-4">{groupName} <span className="text-slate-400 font-normal text-sm ml-2">({groupModels.length})</span></h3>
                      <div className="flex flex-col gap-2">
                        {groupModels.map((m) => (
                          <div key={m.id} className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden bg-white dark:bg-slate-800/50 hover:border-brand-300 dark:hover:border-brand-700 transition-colors">
                            <button
                              onClick={() => setExpandedModel(expandedModel === m.id ? null : m.id)}
                              className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-slate-50/50 dark:hover:bg-slate-800/80 transition-colors"
                            >
                              <div className="grid grid-cols-12 gap-4 w-full items-center">
                                <div className="col-span-4 font-medium text-slate-800 dark:text-slate-100 truncate pr-4">
                                  {m.model_name}
                                </div>
                                <div className="col-span-3 text-xs text-slate-400 dark:text-slate-500 truncate pr-4">
                                  {groupBy === 'provider' ? m.capability?.name : m.provider?.name}
                                </div>
                                <div className="col-span-5 flex items-center justify-between">
                                  <div className="text-xs font-mono text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-900/30 px-2 py-0.5 rounded truncate max-w-full">
                                    {m.pricing_rules?.length > 0
                                      ? m.pricing_rules.filter((r: any) => r.active).map((r: any) => `${r.currency} ${r.price}/${r.unit_type || r.pricing_model}`).join(', ')
                                      : 'No pricing configured'}
                                  </div>
                                  <div className="text-slate-400 text-xs ml-4 flex-shrink-0">
                                    {expandedModel === m.id ? '▲' : '▼'}
                                  </div>
                                </div>
                              </div>
                            </button>

                            {expandedModel === m.id && (
                              <div className="border-t border-slate-100 dark:border-slate-800 p-4 space-y-5 bg-slate-50/50 dark:bg-slate-900/50">
                                <div className="flex justify-end">
                                  <button onClick={() => deleteTechnologyModel(m.id).then(loadAll)} className="text-xs text-coral-500 hover:underline">Delete Model</button>
                                </div>
                                {/* Features */}
                                <div>
                                  <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Features</h4>
                                  <div className="flex flex-wrap gap-2 mb-3">
                                    {m.features?.map((f: any) => (
                                      <span key={f.id} className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300">
                                        <span className="font-medium">{f.feature_key}:</span> {f.feature_value}
                                        <button onClick={() => deleteModelFeature(f.id).then(loadAll)} className="text-slate-400 hover:text-coral-500">×</button>
                                      </span>
                                    ))}
                                  </div>
                                  <form onSubmit={(e) => { e.preventDefault(); handleAddFeature(m.id); }} className="flex gap-2">
                                    <input required placeholder="key (e.g. language)" value={newFeature.feature_key}
                                      onChange={(e) => setNewFeature({ ...newFeature, feature_key: e.target.value })}
                                      className="flex-1 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 text-xs bg-white dark:bg-slate-800" />
                                    <input required placeholder="value" value={newFeature.feature_value}
                                      onChange={(e) => setNewFeature({ ...newFeature, feature_value: e.target.value })}
                                      className="flex-1 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 text-xs bg-white dark:bg-slate-800" />
                                    <button type="submit" className="text-xs bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-300">Add</button>
                                  </form>
                                </div>

                                {/* Pricing */}
                                <div>
                                  <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">Pricing Rules</h4>
                                  <div className="space-y-2 mb-3">
                                    {m.pricing_rules?.map((r: any) => (
                                      <div key={r.id} className="flex flex-col gap-2 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                                        <div className="flex items-center justify-between">
                                          <div className="flex items-center gap-2">
                                            <span className="font-mono font-medium text-slate-800 dark:text-slate-100">{r.currency} {r.price}</span>
                                            <span className="text-slate-400">/ {r.unit_type || r.pricing_model}</span>
                                          </div>
                                          {pricingSourceBadge(r.pricing_source)}
                                        </div>
                                        <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-100 dark:border-slate-700">
                                          <div className="text-slate-400 text-[10px]">
                                            {r.last_verified_on ? `Verified: ${new Date(r.last_verified_on).toLocaleDateString()}` : ''}
                                          </div>
                                          <div className="flex items-center gap-3">
                                            {r.active && r.pricing_source !== 'verified_catalog' && (
                                              <button
                                                onClick={() => updatePricingRule(r.id, { pricing_source: 'verified_catalog', last_verified_on: new Date().toISOString() }).then(loadAll)}
                                                className="text-brand-600 hover:underline"
                                              >
                                                Mark Verified
                                              </button>
                                            )}
                                            <button onClick={() => deletePricingRule(r.id).then(loadAll)} className="text-coral-500 hover:underline">Remove</button>
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                  <form onSubmit={(e) => { e.preventDefault(); handleAddPricing(m.id); }} className="grid grid-cols-2 gap-2 mt-4 p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                                    <div className="col-span-2 text-xs font-semibold text-slate-500 mb-1">Add New Price</div>
                                    <select required value={newPricing.pricing_model} onChange={(e) => setNewPricing({ ...newPricing, pricing_model: e.target.value })}
                                      className="border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 text-xs bg-slate-50 dark:bg-slate-900">
                                      {PRICING_MODELS.map((p) => <option key={p} value={p}>{p}</option>)}
                                    </select>
                                    <input required placeholder="unit (e.g. MINUTE)" value={newPricing.unit_type}
                                      onChange={(e) => setNewPricing({ ...newPricing, unit_type: e.target.value })}
                                      className="border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 text-xs bg-slate-50 dark:bg-slate-900" />
                                    <input required placeholder="price" type="number" step="0.000001" value={newPricing.price}
                                      onChange={(e) => setNewPricing({ ...newPricing, price: e.target.value })}
                                      className="border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 text-xs bg-slate-50 dark:bg-slate-900" />
                                    <select required value={newPricing.pricing_source} onChange={(e) => setNewPricing({ ...newPricing, pricing_source: e.target.value })}
                                      className="border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 text-xs bg-slate-50 dark:bg-slate-900">
                                      {PRICING_SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
                                    </select>
                                    <button type="submit" className="col-span-2 mt-2 text-xs bg-brand-600 text-white px-3 py-2 rounded-lg hover:bg-brand-700 font-medium">
                                      Save Pricing Rule
                                    </button>
                                  </form>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
