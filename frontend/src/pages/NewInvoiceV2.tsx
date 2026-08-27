import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import ClassificationPicker from '../components/ClassificationPicker'
import { getProjectSummary, createInvoice, getBillingPreview } from '../api/client'

export default function NewInvoiceV2() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<any>(null)
  const [billingPreview, setBillingPreview] = useState<any>(null)

  const [items, setItems] = useState<any[]>([])
  // Milestone tasks grouped by their requirement (e.g. "Multilingual Speech-to-Text
  // Integration"), keyed by milestone id. Lets a non-phased milestone be billed one
  // requirement at a time instead of forcing the whole milestone lump sum or a
  // fully manual Custom Line Item.
  const [milestoneReqs, setMilestoneReqs] = useState<Record<string, any[]>>({})

  const [tdsApplicable, setTdsApplicable] = useState(false)
  const [poNumber, setPoNumber] = useState('')
  const [paymentTerms, setPaymentTerms] = useState('')
  const [discountAmount, setDiscountAmount] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (projectId) {
      getProjectSummary(projectId).then(setSummary)
      getBillingPreview(projectId).then((data) => {
        setBillingPreview(data)

        const reqMap: Record<string, any[]> = {}
        data.milestones?.forEach((m: any) => {
          const groups: Record<string, any[]> = {}
          m.tasks?.forEach((t: any) => {
            const key = t.requirement_name || 'Other'
            if (!groups[key]) groups[key] = []
            groups[key].push({
              task_key: t.task_key,
              description: t.description,
              amount: parseFloat(t.amount),
              hours: t.hours != null ? parseFloat(t.hours) : null,
              classification: t.classification || null,
            })
          })
          // Default every requirement to checked, preserving the old
          // behaviour of billing the whole milestone unless the user opts out.
          reqMap[m.id] = Object.entries(groups).map(([requirement_name, tasks]) => ({
            requirement_name,
            tasks,
            totalAmount: tasks.reduce((s, t) => s + t.amount, 0),
            totalHours: tasks.reduce((s, t) => s + (t.hours || 0), 0),
            checked: true,
            classificationOverride: null,
          }))
        })
        setMilestoneReqs(reqMap)
      })
    }
  }, [projectId])

  if (!summary) return null
  const availableComponents = summary.components?.filter((c: any) => 
    c.status === 'AVAILABLE' || c.status === 'PARTIALLY_BILLED' || c.status === 'RESERVED'
  ) || []

  function toggleRequirement(milestoneId: string, reqName: string) {
    setMilestoneReqs((prev) => ({
      ...prev,
      [milestoneId]: prev[milestoneId].map((r) =>
        r.requirement_name === reqName ? { ...r, checked: !r.checked } : r
      ),
    }))
  }

  function setRequirementClassification(milestoneId: string, reqName: string, choice: any) {
    setMilestoneReqs((prev) => ({
      ...prev,
      [milestoneId]: prev[milestoneId].map((r) =>
        r.requirement_name === reqName ? { ...r, classificationOverride: choice } : r
      ),
    }))
  }

  function addItem() {
    setItems([...items, { source_type: 'COMPONENT', source_id: '', task_key: null, requirement_name: null, amount: 0, description: '', classification: null }])
  }

  function removeItem(index: number) {
    const newItems = [...items]
    newItems.splice(index, 1)
    setItems(newItems)
  }

  function updateItem(index: number, field: string, value: any) {
    const newItems = [...items]
    newItems[index][field] = value

    // CUSTOM has no source to pick — clear whatever was selected under a
    // previous source_type and let the user type description/amount directly.
    if (field === 'source_type' && value === 'CUSTOM') {
      newItems[index].source_id = ''
      newItems[index].amount = 0
      newItems[index].description = ''
      newItems[index].classification = null
    }

    // Auto-fill defaults when source_id changes
    if (field === 'source_id') {
      const type = newItems[index].source_type
      if (type === 'COMPONENT') {
        const c = availableComponents.find((x: any) => x.id === value)
        if (c) {
          const remaining = parseFloat(c.amount) - parseFloat(c.billed_amount)
          newItems[index].amount = remaining
          newItems[index].description = `${c.name}`
          newItems[index].classification = null
        }
      }
    }

    setItems(newItems)
  }

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const payloadItems: any[] = [];

      // Checked requirements from the milestone breakdown — each requirement
      // still expands to its underlying task_keys so partial/double-billing
      // tracking stays accurate, but the user only chose at requirement level.
      Object.entries(milestoneReqs).forEach(([milestoneId, reqs]) => {
        (reqs as any[]).forEach((r) => {
          if (!r.checked) return
          r.tasks.forEach((t: any) => {
            payloadItems.push({
              source_type: 'MILESTONE',
              source_id: milestoneId,
              task_key: t.task_key,
              requirement_name: r.requirement_name,
              hours: t.hours,
              amount: t.amount,
              description: t.description,
              billing_classification_id: r.classificationOverride?.id || t.classification?.id || null,
            });
          });
        });
      });

      items.forEach((i) => {
        // Commercial components or manually specified custom line items
        payloadItems.push({
          source_type: i.source_type,
          source_id: i.source_id,
          task_key: i.task_key,
          hours: i.hours ? parseFloat(i.hours) : null,
          amount: parseFloat(i.amount),
          description: i.description,
          billing_classification_id: i.classification?.id,
        });
      });

      await createInvoice(projectId!, {
        items: payloadItems,
        tds_applicable: tdsApplicable,
        po_number: poNumber || null,
        payment_terms: paymentTerms || null,
        discount_amount: discountAmount ? parseFloat(discountAmount) : null,
      })
      navigate(`/invoice/projects/${projectId}`)
    } catch (e: any) {
      setError(e.message || 'Failed to create invoice')
      setSubmitting(false)
    }
  }

  const anyRequirementChecked = Object.values(milestoneReqs).some((reqs: any) => reqs.some((r: any) => r.checked))

  const isValid =
    (anyRequirementChecked || items.length > 0) &&
    items.every((i) => (i.source_type === 'CUSTOM' || i.source_id !== '') && i.amount > 0 && i.description !== '')

  const reqsTitle = `${summary?.delivery_unit_label || 'Milestone'} Requirements to Bill`;

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar showBack title="Create Invoice" subtitle={`Project: ${summary.project_name}`} />
      <div className="p-8 space-y-6 max-w-4xl mx-auto">
        {billingPreview?.milestones?.length > 0 && (
          <Card title={reqsTitle}>
            <div className="space-y-5">
              {billingPreview.milestones.map((m: any) => (
                <div key={m.id} className="rounded-lg border border-slate-200 overflow-hidden">
                  <div className="bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700 border-b border-slate-200">
                    {m.name}
                  </div>
                  <div className="divide-y divide-slate-100">
                    {(milestoneReqs[m.id] || []).map((r: any) => (
                      <div key={r.requirement_name} className="p-3 flex items-start gap-3">
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={r.checked}
                          onChange={() => toggleRequirement(m.id, r.requirement_name)}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-3">
                            <span className="text-sm font-medium text-slate-700 truncate">{r.requirement_name}</span>
                            <span className="text-sm font-semibold text-slate-700 shrink-0">
                              ₹{r.totalAmount.toLocaleString('en-IN')}
                            </span>
                          </div>
                          <div className="text-xs text-slate-400">
                            {r.tasks.length} task{r.tasks.length === 1 ? '' : 's'}
                            {r.totalHours ? ` · ${r.totalHours}h` : ''}
                          </div>
                          {r.checked && (
                            <div className="mt-2 max-w-sm">
                              <ClassificationPicker
                                description={r.requirement_name}
                                value={r.classificationOverride}
                                onChange={(choice) => setRequirementClassification(m.id, r.requirement_name, choice)}
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {(milestoneReqs[m.id] || []).length === 0 && (
                      <div className="p-3 text-xs text-slate-400">No unbilled requirements found for this milestone.</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card title="Other Line Items (Commercial Components / Custom)">
          <div className="space-y-6">

            {items.map((item, index) => (
              <div key={index} className="flex gap-4 items-start p-4 bg-slate-50 rounded-lg border border-slate-200">
                <div className="flex-1 space-y-4">
                  <div className="flex gap-4">
                    <div className="w-1/3">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Source Type</label>
                      <select
                        value={item.source_type}
                        onChange={(e) => updateItem(index, 'source_type', e.target.value)}
                        className="w-full border-slate-200 rounded p-2 text-sm"
                      >
                        <option value="COMPONENT">Commercial Component</option>
                        <option value="CUSTOM">Custom Line Item</option>
                      </select>
                    </div>
                    {item.source_type === 'CUSTOM' ? (
                      <div className="flex-1">
                        <label className="block text-xs font-medium text-slate-500 mb-1">Source Selection</label>
                        <div className="w-full border border-dashed border-slate-200 rounded p-2 text-sm text-slate-400 bg-white">
                          Not tied to a milestone or component — type the description and amount directly →
                        </div>
                      </div>
                    ) : (
                      <div className="flex-1">
                        <label className="block text-xs font-medium text-slate-500 mb-1">Source Selection</label>
                        <select
                          value={item.source_id}
                          onChange={(e) => updateItem(index, 'source_id', e.target.value)}
                          className="w-full border-slate-200 rounded p-2 text-sm"
                        >
                          <option value="">-- Choose --</option>
                          {item.source_type === 'COMPONENT' && availableComponents.map((c: any) => {
                            const remaining = parseFloat(c.amount) - parseFloat(c.billed_amount)
                            return <option key={c.id} value={c.id}>{c.name} (Max ₹{remaining.toLocaleString('en-IN')})</option>
                          })}
                        </select>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Line Item Description</label>
                      <input
                        type="text"
                        value={item.description}
                        onChange={(e) => updateItem(index, 'description', e.target.value)}
                        className="w-full border-slate-200 rounded p-2 text-sm"
                        placeholder="Description to appear on invoice"
                      />
                    </div>
                    <div className="w-1/4">
                      <label className="block text-xs font-medium text-slate-500 mb-1">Amount (₹)</label>
                      <input
                        type="number"
                        value={item.amount}
                        onChange={(e) => updateItem(index, 'amount', e.target.value)}
                        className="w-full border-slate-200 rounded p-2 text-sm"
                      />
                    </div>
                  </div>
                  <ClassificationPicker
                    description={item.description}
                    value={item.classification}
                    noSource={item.source_type === 'CUSTOM'}
                    onChange={(choice) => updateItem(index, 'classification', choice)}
                  />
                </div>
                <button onClick={() => removeItem(index)} className="text-slate-400 hover:text-red-500 p-2">
                  ✕
                </button>
              </div>
            ))}

            <button
              onClick={addItem}
              className="text-sm font-medium text-brand-600 bg-brand-50 px-4 py-2 rounded-lg hover:bg-brand-100"
            >
              + Add Line Item
            </button>

            <div className="pt-4 border-t border-slate-100 grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">PO Number (optional)</label>
                <input
                  type="text"
                  value={poNumber}
                  onChange={(e) => setPoNumber(e.target.value)}
                  className="w-full border-slate-200 rounded p-2 text-sm"
                  placeholder="e.g. PO-2026-045"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Payment Terms (optional)</label>
                <input
                  type="text"
                  value={paymentTerms}
                  onChange={(e) => setPaymentTerms(e.target.value)}
                  className="w-full border-slate-200 rounded p-2 text-sm"
                  placeholder="e.g. Net 30"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Discount (₹, optional)</label>
                <input
                  type="number"
                  min="0"
                  value={discountAmount}
                  onChange={(e) => setDiscountAmount(e.target.value)}
                  className="w-full border-slate-200 rounded p-2 text-sm"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <label className="flex items-center space-x-2 text-sm font-medium text-slate-700">
                <input type="checkbox" checked={tdsApplicable} onChange={(e) => setTdsApplicable(e.target.checked)} />
                <span>Apply TDS Deduction</span>
              </label>
            </div>

            {error && <div className="text-sm text-coral-600 bg-coral-50 p-3 rounded-lg">{error}</div>}

            <div className="pt-4 flex justify-end">
              <button
                disabled={!isValid || submitting}
                onClick={submit}
                className="bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-medium text-sm px-6 py-2.5 rounded-full"
              >
                {submitting ? 'Generating...' : 'Generate Draft Invoice'}
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
