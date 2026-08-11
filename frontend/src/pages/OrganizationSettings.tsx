import { useEffect, useRef, useState } from 'react'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import BackLink from '../components/BackLink'
import { getOrganization, updateOrganization, uploadOrganizationAsset, deleteOrganizationAsset, applyBrandingHistory } from '../api/client'
import ConfirmModal from '../components/ConfirmModal'
import type { OrganizationProfile } from '../api/types'
import { refreshLogo } from '../hooks/useLogo'

type AssetSlotKey = 'logo' | 'signature' | 'seal'

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
const PHONE_RE = /^\d{10}$/
const GSTIN_RE = /^(0[1-9]|[1-2][0-9]|3[0-7])[A-Z]{3}[CPHFATBLJG][A-Z][0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/

const FIELD_ROWS: {
  key: keyof OrganizationProfile
  label: string
  placeholder?: string
  span?: boolean
  multiline?: boolean
  required?: boolean
  maxLength?: number
}[] = [
  { key: 'name', label: 'Company Name', placeholder: 'e.g. Pixous Technologies Pvt Ltd', span: true, required: true, maxLength: 255 },
  { key: 'tagline', label: 'Tagline', placeholder: 'e.g. Strategize · Amplify · Transform', span: true, maxLength: 255 },
  { key: 'address', label: 'Address', placeholder: 'Street, City, State, PIN', span: true, multiline: true, required: true, maxLength: 300 },
  { key: 'email', label: 'Email', placeholder: 'e.g. info@company.com', required: true, maxLength: 100 },
  { key: 'phone', label: 'Phone', placeholder: '10-digit mobile number', required: true, maxLength: 10 },
  { key: 'website', label: 'Website', placeholder: 'e.g. https://company.com', maxLength: 100 },
  { key: 'gstin', label: 'GSTIN', placeholder: 'e.g. 22AAAAA0000A1Z5', required: true, maxLength: 15 },
  { key: 'registration_number', label: 'Registration Number', placeholder: 'e.g. U72900TN2020PTC123456', maxLength: 50 },
  { key: 'certifications', label: 'Certifications', placeholder: 'e.g. ISO 9001:2015 · CMMI Level 3', span: true, multiline: true, maxLength: 500 },
  { key: 'signatory_name', label: 'Authorized Signatory Name', placeholder: 'e.g. Jane Doe', maxLength: 100 },
  { key: 'signatory_title', label: 'Signatory Title', placeholder: 'e.g. Authorized Signatory', maxLength: 100 },
  { key: 'invoice_terms', label: 'Invoice Terms & Conditions', placeholder: 'Enter terms, one per line', span: true, multiline: true, maxLength: 2000 },
]

const BANK_FIELD_ROWS: { key: keyof OrganizationProfile; label: string; placeholder?: string; maxLength?: number }[] = [
  { key: 'bank_name', label: 'Bank Name', placeholder: 'e.g. HDFC Bank', maxLength: 100 },
  { key: 'bank_account_number', label: 'Account Number', placeholder: 'e.g. 000123456789', maxLength: 30 },
  { key: 'bank_ifsc', label: 'IFSC Code', placeholder: 'e.g. HDFC0001234', maxLength: 11 },
  { key: 'bank_branch', label: 'Branch', placeholder: 'e.g. Gandhipuram, Coimbatore', maxLength: 100 },
]

function formatGSTIN(val: string): string {
  const v = val.toUpperCase().replace(/[^A-Z0-9]/g, '')
  let filtered = ''
  for (let i = 0; i < v.length && filtered.length < 15; i++) {
    const c = v[i]
    const pos = filtered.length
    if (pos < 2 && /[0-9]/.test(c)) filtered += c
    else if (pos >= 2 && pos < 7 && /[A-Z]/.test(c)) filtered += c
    else if (pos >= 7 && pos < 11 && /[0-9]/.test(c)) filtered += c
    else if (pos === 11 && /[A-Z]/.test(c)) filtered += c
    else if (pos === 12 && /[1-9A-Z]/.test(c)) filtered += c
    else if (pos === 13 && c === 'Z') filtered += c
    else if (pos === 14 && /[0-9A-Z]/.test(c)) filtered += c
  }
  return filtered
}

function validateField(key: keyof OrganizationProfile, value: string, required?: boolean): string | null {
  if (!value) return required ? 'This field is required' : null
  if (key === 'email' && !EMAIL_RE.test(value)) return 'Enter a valid email address'
  if (key === 'phone' && !PHONE_RE.test(value)) return 'Enter a valid 10-digit mobile number'
  if (key === 'gstin' && !GSTIN_RE.test(value.toUpperCase())) return 'Enter a valid GSTIN, e.g. 22AAAAA0000A1Z5'
  return null
}

export default function OrganizationSettings() {
  const [profile, setProfile] = useState<OrganizationProfile | null>(null)
  const [savedProfile, setSavedProfile] = useState<OrganizationProfile | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [bankExpanded, setBankExpanded] = useState(false)
  const [removeConfirm, setRemoveConfirm] = useState<AssetSlotKey | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof OrganizationProfile, string>>>({})
  const [updateHistory, setUpdateHistory] = useState(false)

  useEffect(() => {
    getOrganization()
      .then((r) => {
        setProfile(r.profile)
        setSavedProfile(r.profile)
        // Auto-expand if bank details were already filled in, so existing
        // data isn't hidden behind a collapsed section by surprise.
        if (BANK_FIELD_ROWS.some((f) => (r.profile as any)[f.key])) {
          setBankExpanded(true)
        }
      })
      .catch((e) => setError(e.message))
  }, [])

  async function save() {
    if (!profile) return
    const errors: Partial<Record<keyof OrganizationProfile, string>> = {}
    for (const f of FIELD_ROWS) {
      const msg = validateField(f.key, ((profile[f.key] as string) || '').trim(), f.required)
      if (msg) errors[f.key] = msg
    }
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) {
      setError('Please fix the highlighted fields before saving.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const { logo_path, signature_path, seal_path, ...fields } = profile
      const r = await updateOrganization(fields)
      const updated = { ...r.profile, logo_path, signature_path, seal_path }
      setProfile(updated)
      setSavedProfile(updated)
      setSaved(true)
      setIsDirty(false)
      if (updateHistory) {
        await applyBrandingHistory()
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  function discard() {
    if (!savedProfile) return
    setProfile(savedProfile)
    setSaved(false)
    setIsDirty(false)
    setError(null)
    setFieldErrors({})
  }

  async function handleAssetUpload(slot: AssetSlotKey, file: File) {
    setError(null)
    try {
      const r = await uploadOrganizationAsset(slot, file)
      const newPath = (r.profile as any)[`${slot}_path`]
      setProfile((prev) => prev ? { ...prev, [`${slot}_path`]: newPath } : r.profile)
      if (slot === 'logo') refreshLogo(newPath)
      if (updateHistory) {
        await applyBrandingHistory()
      }
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function handleAssetRemove(slot: AssetSlotKey) {
    setError(null)
    try {
      const r = await deleteOrganizationAsset(slot)
      setProfile((prev) => prev ? { ...prev, [`${slot}_path`]: (r.profile as any)[`${slot}_path`] } : r.profile)
      if (slot === 'logo') refreshLogo(null)
      if (updateHistory) {
        await applyBrandingHistory()
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRemoveConfirm(null)
    }
  }

  return (
    <div className="flex-1">
      <BackLink />
      <Topbar title="Organization Settings" subtitle="Branding shown on every generated document — quotation, BRD, SRS, and invoice." />
      <div className="p-8 max-w-3xl space-y-6">
        {error && <div className="text-sm text-coral-600 bg-coral-50 rounded-2xl px-4 py-3">{error}</div>}

        {!profile ? (
          <p className="text-sm text-slate-400">Loading…</p>
        ) : (
          <>
            <Card
              title="Company Details"
              action={
                <div className="flex items-center gap-3">
                  {saved && !isDirty && <span className="text-xs text-brand-600 font-medium">Saved ✓</span>}
                  {isDirty && (
                    <button
                      onClick={discard}
                      className="text-sm font-medium text-slate-500 hover:text-slate-700 px-5 py-2 rounded-full border border-slate-200 hover:border-slate-300 transition-colors"
                    >
                      Discard
                    </button>
                  )}
                  <button
                    disabled={saving}
                    onClick={save}
                    className="text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white px-5 py-2 rounded-full disabled:bg-slate-200"
                  >
                    {saving ? 'Saving…' : 'Save Changes'}
                  </button>
                </div>
              }
            >
              <div className="grid grid-cols-2 gap-4">
                {FIELD_ROWS.map((f) => (
                  <div key={f.key} className={f.span ? 'col-span-2' : ''}>
                    <label className="text-xs font-medium text-slate-500">
                      {f.label}
                      {f.required && <span className="text-coral-600 ml-0.5">*</span>}
                    </label>
                    {f.multiline ? (
                      <textarea
                        value={(profile[f.key] as string) || ''}
                        placeholder={f.placeholder}
                        maxLength={f.maxLength}
                        rows={3}
                        onChange={(e) => {
                          setProfile({ ...profile, [f.key]: e.target.value })
                          setSaved(false)
                          setIsDirty(true)
                          setFieldErrors((prev) => ({ ...prev, [f.key]: undefined }))
                        }}
                        className={`mt-1 w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-none ${fieldErrors[f.key] ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                      />
                    ) : (
                      <input
                        value={(profile[f.key] as string) || ''}
                        placeholder={f.placeholder}
                        maxLength={f.maxLength}
                        type={f.key === 'email' ? 'email' : f.key === 'phone' ? 'tel' : 'text'}
                        inputMode={f.key === 'phone' ? 'numeric' : undefined}
                        onChange={(e) => {
                          const v =
                            f.key === 'phone'
                              ? e.target.value.replace(/\D/g, '')
                              : f.key === 'gstin'
                                ? formatGSTIN(e.target.value)
                                : e.target.value
                          setProfile({ ...profile, [f.key]: v })
                          setSaved(false)
                          setIsDirty(true)
                          setFieldErrors((prev) => ({ ...prev, [f.key]: undefined }))
                        }}
                        className={`mt-1 w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${fieldErrors[f.key] ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                      />
                    )}
                    {fieldErrors[f.key] && <p className="text-xs text-coral-600 mt-1">{fieldErrors[f.key]}</p>}
                  </div>
                ))}
              </div>
            </Card>

            <Card
              title="Bank Details (used on Invoices only)"
              action={
                <button
                  onClick={() => setBankExpanded((v) => !v)}
                  className="text-xs font-medium text-slate-500 hover:text-slate-700"
                >
                  {bankExpanded ? 'Hide' : 'Show'}
                </button>
              }
            >
              {bankExpanded ? (
                <div className="grid grid-cols-2 gap-4">
                  {BANK_FIELD_ROWS.map((f) => (
                    <div key={f.key}>
                      <label className="text-xs font-medium text-slate-500">{f.label}</label>
                      <input
                        value={(profile[f.key] as string) || ''}
                        placeholder={f.placeholder}
                        maxLength={f.maxLength}
                        onChange={(e) => {
                          setProfile({ ...profile, [f.key]: e.target.value })
                          setSaved(false)
                          setIsDirty(true)
                        }}
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400">
                  Only needed when generating invoices — not used anywhere else in the estimation workflow.
                  Click "Show" to view or edit.
                </p>
              )}
            </Card>

            <Card title="Branding Assets">
              <div className="grid grid-cols-3 gap-5">
                <AssetSlot
                  label="Logo"
                  path={profile.logo_path}
                  onUpload={(f) => handleAssetUpload('logo', f)}
                  onRemove={() => setRemoveConfirm('logo')}
                />
                <AssetSlot
                  label="Signature"
                  path={profile.signature_path}
                  onUpload={(f) => handleAssetUpload('signature', f)}
                  onRemove={() => setRemoveConfirm('signature')}
                />
                <AssetSlot
                  label="Company Seal"
                  path={profile.seal_path}
                  onUpload={(f) => handleAssetUpload('seal', f)}
                  onRemove={() => setRemoveConfirm('seal')}
                />
              </div>
              <p className="text-xs text-slate-400 mt-4">
                These appear automatically on every quotation, BRD, SRS, and invoice — logo in the header, signature
                and seal above the authorized signatory line.
              </p>
              <div className="mt-6 pt-4 border-t border-slate-100">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={updateHistory}
                    onChange={(e) => setUpdateHistory(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
                  />
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-slate-700 group-hover:text-slate-900">
                      Apply branding changes to all previously generated documents
                    </span>
                    <span className="text-xs text-slate-500">
                      Retroactively updates the letterhead, logo, and signature block in existing historical invoices and documents.
                    </span>
                  </div>
                </label>
              </div>
            </Card>
          </>
        )}
      </div>

      <ConfirmModal
        isOpen={removeConfirm !== null}
        title="Remove branding asset?"
        message={`This will remove the ${removeConfirm ?? ''} from every future generated document until you upload a new one.`}
        confirmText="Remove"
        onConfirm={() => removeConfirm && handleAssetRemove(removeConfirm)}
        onCancel={() => setRemoveConfirm(null)}
      />
    </div>
  )
}

function AssetSlot({
  label,
  path,
  onUpload,
  onRemove,
}: {
  label: string
  path: string | null
  onUpload: (f: File) => void
  onRemove: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <div>
      <div
        onClick={() => {
          // An asset already occupies this slot — require explicit removal
          // before a new one can be uploaded, instead of silently replacing it.
          if (!path) inputRef.current?.click()
        }}
        className={`relative aspect-square rounded-2xl bg-slate-50 border-2 border-dashed flex items-center justify-center overflow-hidden ${path ? 'border-slate-200' : 'border-slate-200 hover:border-brand-300 cursor-pointer'}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onUpload(f)
          }}
        />
        {path ? (
          <>
            <img src={`/branding/${path}?t=${Date.now()}`} alt={label} className="w-full h-full object-contain p-3" />
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRemove()
              }}
              title={`Remove ${label} (required before uploading a new one)`}
              className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-white shadow-card text-slate-500 hover:text-coral-600 hover:bg-coral-50 flex items-center justify-center text-sm leading-none"
            >
              ×
            </button>
          </>
        ) : (
          <span className="text-xs text-slate-400 text-center px-2">Click to upload</span>
        )}
      </div>
      <div className="text-xs font-medium text-slate-600 text-center mt-2">{label}</div>
    </div>
  )
}
