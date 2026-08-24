import { useState, useEffect } from 'react'
import { patchEstimationClient, listDbClients } from '../api/client'
import Card from './Card'
import { EMAIL_RE, PHONE_RE, GSTIN_RE, formatGSTIN, formatPhone, uiFormatPhone } from '../utils/validation'

export default function ClientDetailsEditor({ baseName, clientInfo, onSaved }: { baseName: string, clientInfo: any, onSaved: (newInfo: any) => void }) {
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [existingClients, setExistingClients] = useState<any[]>([])

  useEffect(() => {
    if (isEditing) {
      listDbClients().then(res => setExistingClients(res.clients)).catch(console.error)
    }
  }, [isEditing])
  
  const [form, setForm] = useState({
    company_name: clientInfo?.company_name || '',
    contact_person: clientInfo?.contact_person || '',
    email: clientInfo?.email || '',
    phone: clientInfo?.phone || '',
    gstin: clientInfo?.gstin || '',
    billing_address: clientInfo?.billing_address || '',
  })

  // Calculate completeness
  const requiredFields = ['company_name', 'contact_person']
  const optionalFields = ['email', 'phone', 'gstin', 'billing_address']
  const allFields = [...requiredFields, ...optionalFields]
  
  const filledFields = allFields.filter(f => form[f as keyof typeof form]?.trim().length > 0)
  const completeness = Math.round((filledFields.length / allFields.length) * 100)
  const isConfirmed = clientInfo?.status === 'CONFIRMED'
  const hasMinRequired = form.company_name.trim().length > 0 || form.contact_person.trim().length > 0

  const handleSave = async (confirm: boolean = false) => {
    const errors: Record<string, string> = {}
    if (confirm && !hasMinRequired) {
      errors.general = 'At least Company Name or Contact Person is required to confirm.'
    }
    
    if (form.email && !EMAIL_RE.test(form.email)) {
      errors.email = 'Enter a valid email address'
    }
    if (form.phone && !PHONE_RE.test(formatPhone(form.phone))) {
      errors.phone = 'Enter a valid 10-digit Indian mobile number'
    }
    if (form.gstin && !GSTIN_RE.test(form.gstin.toUpperCase())) {
      errors.gstin = 'Enter a valid GSTIN, e.g. 22AAAAA0000A1Z5'
    }

    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) {
      if (errors.general) setError(errors.general)
      else setError('Please fix the highlighted fields before saving.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const payload = {
        company_name: form.company_name || null,
        contact_person: form.contact_person || null,
        email: form.email || null,
        phone: form.phone || null,
        gstin: form.gstin || null,
        billing_address: form.billing_address || null,
        status: confirm ? 'CONFIRMED' : (clientInfo?.status || 'DRAFT')
      }
      await patchEstimationClient(baseName, payload)
      onSaved(payload)
      setIsEditing(false)
    } catch (err: any) {
      setError(err.message || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (!isEditing) {
    return (
      <Card className="mb-6 p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold tracking-tight text-slate-900 flex items-center gap-2">
              Client Identity
              {isConfirmed ? (
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">CONFIRMED</span>
              ) : (
                <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-bold rounded">DRAFT</span>
              )}
            </h3>
            <p className="text-sm text-slate-500 mt-1">Review the AI-extracted identity and confirm to proceed to project conversion.</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="text-sm font-medium text-slate-600">Profile Completeness: {completeness}%</div>
            <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 transition-all" style={{ width: `${completeness}%` }} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-6">
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Company / Organization</div>
            <div className="text-sm font-medium text-slate-900">{clientInfo?.company_name || <span className="text-slate-400 italic">Not specified</span>}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Contact Person</div>
            <div className="text-sm font-medium text-slate-900">{clientInfo?.contact_person || <span className="text-slate-400 italic">Not specified</span>}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Email Address</div>
            <div className="text-sm font-medium text-slate-900">{clientInfo?.email || <span className="text-slate-400 italic">Not specified</span>}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Phone Number</div>
            <div className="text-sm font-medium text-slate-900">{clientInfo?.phone || <span className="text-slate-400 italic">Not specified</span>}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">GSTIN / Tax ID</div>
            <div className="text-sm font-medium text-slate-900">{clientInfo?.gstin || <span className="text-slate-400 italic">Not specified</span>}</div>
          </div>
          <div className="col-span-2 md:col-span-1">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Billing Address</div>
            <div className="text-sm font-medium text-slate-900 whitespace-pre-wrap">{clientInfo?.billing_address || <span className="text-slate-400 italic">Not specified</span>}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 border-t border-slate-100 pt-4 mt-2">
          <button onClick={() => setIsEditing(true)} className="px-4 py-2 bg-slate-100 text-slate-700 hover:bg-slate-200 text-sm font-semibold rounded-lg transition-colors">
            Edit Details
          </button>
          {!isConfirmed && (
            <button 
              onClick={() => handleSave(true)}
              disabled={saving || !hasMinRequired}
              className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? 'Confirming...' : 'Confirm Identity'}
            </button>
          )}
        </div>
      </Card>
    )
  }

  return (
    <Card className="mb-6 p-6 border-blue-200 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
      <h3 className="text-lg font-semibold tracking-tight text-slate-900 mb-4">Edit Client Details</h3>
      
      {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg mb-4">{error}</div>}

      {existingClients.length > 0 && (
        <div className="mb-6 bg-slate-50 p-4 rounded-xl border border-slate-200">
          <label className="block text-sm font-semibold text-slate-700 mb-2">Populate from Existing Client</label>
          <select 
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm bg-white"
            onChange={(e) => {
              const id = e.target.value
              if (!id) return
              const c = existingClients.find(x => x.id === id)
              if (c) {
                setForm({
                  company_name: c.company_name || '',
                  contact_person: c.contact_person || '',
                  email: c.email || '',
                  phone: c.phone || '',
                  gstin: c.gstin || '',
                  billing_address: c.billing_address || ''
                })
                setFieldErrors({})
                // Reset select back to default option after picking
                e.target.value = ''
              }
            }}
          >
            <option value="">-- Select a client to autofill --</option>
            {existingClients.map(c => (
              <option key={c.id} value={c.id}>
                {c.company_name} {c.contact_person ? `(${c.contact_person})` : ''}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Company / Organization Name</label>
          <input 
            type="text" 
            value={form.company_name} 
            onChange={e => {
              setForm({...form, company_name: e.target.value})
              setFieldErrors({...fieldErrors, company_name: ''})
            }}
            className={`w-full px-3 py-2 border rounded-lg focus:ring-2 outline-none text-sm ${fieldErrors.company_name ? 'border-red-300 focus:ring-red-200' : 'border-slate-300 focus:ring-blue-500'}`}
            placeholder="e.g. Acme Corp"
          />
          {fieldErrors.company_name && <p className="text-xs text-red-600 mt-1">{fieldErrors.company_name}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Contact Person</label>
          <input 
            type="text" 
            value={form.contact_person} 
            onChange={e => {
              setForm({...form, contact_person: e.target.value})
              setFieldErrors({...fieldErrors, contact_person: ''})
            }}
            className={`w-full px-3 py-2 border rounded-lg focus:ring-2 outline-none text-sm ${fieldErrors.contact_person ? 'border-red-300 focus:ring-red-200' : 'border-slate-300 focus:ring-blue-500'}`}
            placeholder="e.g. Jane Doe"
          />
          {fieldErrors.contact_person && <p className="text-xs text-red-600 mt-1">{fieldErrors.contact_person}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
          <input 
            type="email" 
            value={form.email} 
            onChange={e => {
              setForm({...form, email: e.target.value})
              setFieldErrors({...fieldErrors, email: ''})
            }}
            className={`w-full px-3 py-2 border rounded-lg focus:ring-2 outline-none text-sm ${fieldErrors.email ? 'border-red-300 focus:ring-red-200' : 'border-slate-300 focus:ring-blue-500'}`}
          />
          {fieldErrors.email && <p className="text-xs text-red-600 mt-1">{fieldErrors.email}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Phone</label>
          <input 
            type="tel" 
            inputMode="numeric"
            value={form.phone ? uiFormatPhone(form.phone) : ''} 
            onChange={e => {
              setForm({...form, phone: uiFormatPhone(e.target.value)})
              setFieldErrors({...fieldErrors, phone: ''})
            }}
            className={`w-full px-3 py-2 border rounded-lg focus:ring-2 outline-none text-sm ${fieldErrors.phone ? 'border-red-300 focus:ring-red-200' : 'border-slate-300 focus:ring-blue-500'}`}
          />
          {fieldErrors.phone && <p className="text-xs text-red-600 mt-1">{fieldErrors.phone}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">GSTIN / Tax ID</label>
          <input 
            type="text" 
            value={form.gstin} 
            onChange={e => {
              setForm({...form, gstin: formatGSTIN(e.target.value)})
              setFieldErrors({...fieldErrors, gstin: ''})
            }}
            className={`w-full px-3 py-2 border rounded-lg focus:ring-2 outline-none text-sm ${fieldErrors.gstin ? 'border-red-300 focus:ring-red-200' : 'border-slate-300 focus:ring-blue-500'}`}
          />
          {fieldErrors.gstin && <p className="text-xs text-red-600 mt-1">{fieldErrors.gstin}</p>}
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Billing Address</label>
          <textarea 
            value={form.billing_address} 
            onChange={e => {
              setForm({...form, billing_address: e.target.value})
              setFieldErrors({...fieldErrors, billing_address: ''})
            }}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm h-24"
          />
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        <button 
          onClick={() => setIsEditing(false)} 
          className="px-4 py-2 text-slate-600 hover:bg-slate-100 text-sm font-semibold rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button 
          onClick={() => handleSave(false)} 
          disabled={saving}
          className="px-4 py-2 bg-slate-800 text-white hover:bg-slate-900 text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
        <button 
          onClick={() => handleSave(true)} 
          disabled={saving || !hasMinRequired}
          className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 text-sm font-semibold rounded-lg transition-colors ml-auto disabled:opacity-50"
        >
          {saving ? 'Confirming...' : 'Save & Confirm Identity'}
        </button>
      </div>
    </Card>
  )
}
