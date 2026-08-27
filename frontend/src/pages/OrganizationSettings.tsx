import { useEffect, useRef, useState } from 'react'
import { useNavigate, useBlocker } from 'react-router-dom'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import { getOrganization, updateOrganization, uploadOrganizationAsset, deleteOrganizationAsset, applyBrandingHistory } from '../api/client'
import ConfirmModal from '../components/ConfirmModal'
import type { OrganizationProfile } from '../api/types'
import { refreshLogo } from '../hooks/useLogo'

type AssetSlotKey = 'logo' | 'signature' | 'seal'

import { EMAIL_RE, PHONE_RE, GSTIN_RE, WEBSITE_RE, UPI_ID_RE } from '../utils/validation'
import { formatGSTIN, formatPhone, uiFormatPhone } from '../utils/validation'

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
  { key: 'phone', label: 'Phone', placeholder: '10-digit mobile number', required: true, maxLength: 20 },
  { key: 'website', label: 'Website', placeholder: 'e.g. https://company.com', maxLength: 100 },
  { key: 'gstin', label: 'GSTIN', placeholder: 'e.g. 22AAAAA0000A1Z5', required: true, maxLength: 15 },
  { key: 'registration_number', label: 'Registration Number', placeholder: 'e.g. U72900TN2020PTC123456', maxLength: 50 },
  { key: 'certifications', label: 'Certifications', placeholder: 'e.g. ISO 9001:2015 · CMMI Level 3', span: true, multiline: true, maxLength: 500 },
  { key: 'signatory_name', label: 'Authorized Signatory Name', placeholder: 'e.g. Jane Doe', maxLength: 100 },
  { key: 'signatory_title', label: 'Signatory Title', placeholder: 'e.g. Authorized Signatory', maxLength: 100 },
  { key: 'invoice_terms', label: 'Invoice Terms & Conditions (Max 100 words)', placeholder: 'Enter terms, one per line', span: true, multiline: true, maxLength: 2000 },
]

const BANK_FIELD_ROWS: { key: keyof OrganizationProfile; label: string; placeholder?: string; maxLength?: number }[] = [
  { key: 'bank_name', label: 'Bank Name', placeholder: 'e.g. HDFC Bank', maxLength: 100 },
  { key: 'bank_account_number', label: 'Account Number', placeholder: 'e.g. 000123456789', maxLength: 30 },
  { key: 'bank_ifsc', label: 'IFSC Code', placeholder: 'e.g. HDFC0001234', maxLength: 11 },
  { key: 'bank_branch', label: 'Branch', placeholder: 'e.g. Gandhipuram, Coimbatore', maxLength: 100 },
  { key: 'upi_id', label: 'UPI ID', placeholder: 'e.g. company@okhdfcbank', maxLength: 100 },
]



function truncateWords(val: string, max: number): string {
  const tokens = val.split(/(\s+)/)
  let wordCount = 0
  let result = ''
  for (const token of tokens) {
    if (token.trim().length > 0) {
      wordCount++
      if (wordCount > max) break
    }
    result += token
  }
  return result
}

function validateField(key: keyof OrganizationProfile, value: string, required?: boolean): string | null {
  if (!value) return required ? 'This field is required' : null
  if (key === 'email' && !EMAIL_RE.test(value)) return 'Enter a valid email address'
  if (key === 'phone' && !PHONE_RE.test(formatPhone(value))) return 'Enter a valid 10-digit Indian mobile number'
  if (key === 'website' && value && !WEBSITE_RE.test(value)) return 'Enter a valid website URL'
  if (key === 'gstin' && !GSTIN_RE.test(value.toUpperCase())) return 'Enter a valid GSTIN, e.g. 22AAAAA0000A1Z5'
  if (key === 'bank_name' && !/^[A-Za-z\s.]+$/.test(value)) return 'Bank name should contain only letters and spaces'
  if (key === 'bank_account_number' && !/^\d{9,18}$/.test(value)) return 'Enter a valid bank account number (9-18 digits)'
  if (key === 'bank_ifsc' && !/^[A-Z]{4}0[0-9]{6}$/.test(value.toUpperCase())) return 'Enter a valid IFSC code (e.g., SBIN0125620)'
  if (key === 'upi_id' && !UPI_ID_RE.test(value)) return 'Enter a valid UPI ID (e.g., name@bank)'
  
  if (key === 'invoice_terms') {
    const wordCount = value.trim().split(/\s+/).filter((w) => w.length > 0).length
    if (wordCount > 100) return `Terms cannot exceed 100 words (currently ${wordCount})`
  }

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
  const [pendingAssets, setPendingAssets] = useState<Partial<Record<AssetSlotKey, File | null>>>({})
  const [pendingAssetUrls, setPendingAssetUrls] = useState<Partial<Record<AssetSlotKey, string>>>({})
  const navigate = useNavigate()
  const [showBackConfirm, setShowBackConfirm] = useState(false)

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirty && currentLocation.pathname !== nextLocation.pathname
  )

  useEffect(() => {
    if (blocker.state === 'blocked') {
      let hasErrors = false
      for (const f of FIELD_ROWS) {
        if (validateField(f.key, ((profile?.[f.key] as string) || '').trim(), f.required)) hasErrors = true
      }
      for (const f of BANK_FIELD_ROWS) {
        if (validateField(f.key, ((profile?.[f.key] as string) || '').trim(), false)) hasErrors = true
      }
      
      if (hasErrors) {
        save(false)
        blocker.reset()
      } else {
        setShowBackConfirm(true)
      }
    }
  }, [blocker.state, profile, isDirty])

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

  async function save(navigateAfterSuccess = false) {
    if (!profile) return false
    const errors: Partial<Record<keyof OrganizationProfile, string>> = {}
    for (const f of FIELD_ROWS) {
      const msg = validateField(f.key, ((profile[f.key] as string) || '').trim(), f.required)
      if (msg) errors[f.key] = msg
    }
    for (const f of BANK_FIELD_ROWS) {
      const msg = validateField(f.key, ((profile[f.key] as string) || '').trim(), false)
      if (msg) errors[f.key] = msg
    }
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) {
      setError('Please fix the highlighted fields before saving.')
      window.scrollTo({ top: 0, behavior: 'smooth' })
      return false
    }
    setSaving(true)
    setError(null)
    try {
      let updatedProfile = { ...profile }
      for (const slot of ['logo', 'signature', 'seal'] as AssetSlotKey[]) {
        if (pendingAssets[slot] === null) {
          const r = await deleteOrganizationAsset(slot)
          updatedProfile = { ...updatedProfile, [`${slot}_path`]: (r.profile as any)[`${slot}_path`] }
          if (slot === 'logo') refreshLogo(null)
        } else if (pendingAssets[slot]) {
          const r = await uploadOrganizationAsset(slot, pendingAssets[slot]!)
          updatedProfile = { ...updatedProfile, [`${slot}_path`]: (r.profile as any)[`${slot}_path`] }
          if (slot === 'logo') refreshLogo((r.profile as any)[`${slot}_path`])
        }
      }

      const { logo_path, signature_path, seal_path, ...fields } = updatedProfile
      if (fields.phone) {
        fields.phone = formatPhone(fields.phone as string)
      }
      const r = await updateOrganization(fields)
      const finalUpdated = { ...r.profile, logo_path, signature_path, seal_path }
      setProfile(finalUpdated)
      setSavedProfile(finalUpdated)
      setSaved(true)
      setIsDirty(false)
      Object.values(pendingAssetUrls).forEach(url => { if (url && url.startsWith('blob:')) URL.revokeObjectURL(url) })
      setPendingAssets({})
      setPendingAssetUrls({})
      
      if (updateHistory) {
        await applyBrandingHistory()
      }
      if (navigateAfterSuccess) {
        navigate(-1)
      }
      return true
    } catch (e: any) {
      setError(e.message)
      return false
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
    Object.values(pendingAssetUrls).forEach(url => { if (url && url.startsWith('blob:')) URL.revokeObjectURL(url) })
    setPendingAssets({})
    setPendingAssetUrls({})
  }

  function handleAssetUpload(slot: AssetSlotKey, file: File) {
    setPendingAssets((prev) => ({ ...prev, [slot]: file }))
    setPendingAssetUrls((prev) => ({ ...prev, [slot]: URL.createObjectURL(file) }))
    setIsDirty(true)
    setSaved(false)
  }

  function handleAssetRemove(slot: AssetSlotKey) {
    setPendingAssets((prev) => ({ ...prev, [slot]: null }))
    setPendingAssetUrls((prev) => {
      const prevUrl = prev[slot]
      if (prevUrl && prevUrl.startsWith('blob:')) URL.revokeObjectURL(prevUrl)
      return { ...prev, [slot]: undefined }
    })
    setIsDirty(true)
    setSaved(false)
    setRemoveConfirm(null)
  }

  const uploadInputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar showBack title="Organization Settings" subtitle="Branding shown on every generated document — quotation, BRD, SRS, and invoice." />
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
                    onClick={() => save(false)}
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
                    <div className="relative">
                      {f.multiline ? (
                        <>
                          <textarea
                            value={(profile[f.key] as string) || ''}
                            placeholder={f.placeholder}
                            maxLength={f.maxLength}
                            rows={3}
                            onChange={(e) => {
                              let val = e.target.value
                              setProfile({ ...profile, [f.key]: val })
                              setSaved(false)
                              setIsDirty(true)
                              setFieldErrors((prev) => ({ ...prev, [f.key]: undefined }))
                            }}
                            className={`mt-1 w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 resize-none ${f.key === 'invoice_terms' ? 'pb-8' : ''} ${fieldErrors[f.key] || (f.key === 'invoice_terms' && ((profile[f.key] as string) || '').trim().split(/\s+/).filter(Boolean).length > 100) ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                          />
                          {f.key === 'invoice_terms' && (() => {
                            const val = (profile[f.key] as string) || ''
                            const count = val.trim().split(/\s+/).filter(Boolean).length
                            const isOver = count > 100
                            return (
                              <div
                                className={`absolute bottom-3 right-3 text-[10px] font-medium transition-colors ${isOver ? 'text-coral-600 bg-coral-50 px-1.5 py-0.5 rounded flex items-center gap-1 shadow-sm' : 'text-slate-400'}`}
                              >
                                {isOver && (
                                  <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                                )}
                                {count} / 100 words
                              </div>
                            )
                          })()}
                        </>
                      ) : (
                      <input
                        value={
                          f.key === 'phone' && profile[f.key]
                            ? uiFormatPhone(profile[f.key] as string)
                            : (profile[f.key] as string) || ''
                        }
                        placeholder={f.placeholder}
                        maxLength={f.maxLength}
                        type={f.key === 'email' ? 'email' : f.key === 'phone' ? 'tel' : 'text'}
                        inputMode={f.key === 'phone' ? 'numeric' : undefined}
                        onChange={(e) => {
                          let v = e.target.value
                          if (f.key === 'phone') {
                            v = uiFormatPhone(v)
                          } else if (f.key === 'gstin') {
                            v = formatGSTIN(v)
                          }
                          setProfile({ ...profile, [f.key]: v })
                          setSaved(false)
                          setIsDirty(true)
                          setFieldErrors((prev) => ({ ...prev, [f.key]: undefined }))
                        }}
                        className={`mt-1 w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${fieldErrors[f.key] ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                      />
                    )}
                    </div>
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
                          let v = e.target.value
                          if (f.key === 'bank_name') {
                            v = v.replace(/[^A-Za-z\s.]/g, '')
                          }
                          if (f.key === 'bank_account_number') {
                            v = v.replace(/\D/g, '')
                          }
                          if (f.key === 'bank_ifsc') {
                            let raw = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
                            let formatted = ''
                            for (let i = 0; i < raw.length && i < 11; i++) {
                              if (i < 4) {
                                if (/[A-Z]/.test(raw[i])) formatted += raw[i]
                              } else if (i === 4) {
                                if (raw[i] === '0' || raw[i] === 'O') {
                                  formatted += '0'
                                }
                              } else {
                                if (/[0-9]/.test(raw[i])) formatted += raw[i]
                              }
                            }
                            v = formatted
                          }
                          
                          setProfile({ ...profile, [f.key]: v })
                          setSaved(false)
                          setIsDirty(true)
                          setFieldErrors((prev) => ({ ...prev, [f.key]: undefined }))
                        }}
                        className={`mt-1 w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${fieldErrors[f.key] ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                      />
                      {fieldErrors[f.key] && <p className="text-xs text-coral-600 mt-1">{fieldErrors[f.key]}</p>}
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
                  src={pendingAssets.logo === null ? null : (pendingAssetUrls.logo || (profile.logo_path ? `/branding/${profile.logo_path}?t=${Date.now()}` : null))}
                  onUpload={(f) => handleAssetUpload('logo', f)}
                  onRemove={() => setRemoveConfirm('logo')}
                />
                <AssetSlot
                  label="Signature"
                  src={pendingAssets.signature === null ? null : (pendingAssetUrls.signature || (profile.signature_path ? `/branding/${profile.signature_path}?t=${Date.now()}` : null))}
                  onUpload={(f) => handleAssetUpload('signature', f)}
                  onRemove={() => setRemoveConfirm('signature')}
                />
                <AssetSlot
                  label="Company Seal"
                  src={pendingAssets.seal === null ? null : (pendingAssetUrls.seal || (profile.seal_path ? `/branding/${profile.seal_path}?t=${Date.now()}` : null))}
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

      <ConfirmModal
        isOpen={showBackConfirm}
        title="Unsaved Changes"
        message="You have unsaved changes. Would you like to save them before leaving?"
        confirmText="Save & Leave"
        cancelText="Discard & Leave"
        onConfirm={async () => {
          const success = await save(false)
          if (success) {
            setShowBackConfirm(false)
            if (blocker.state === 'blocked') blocker.proceed()
            else navigate(-1)
          } else {
            setShowBackConfirm(false)
            if (blocker.state === 'blocked') blocker.reset()
          }
        }}
        onCancel={() => {
          discard()
          setShowBackConfirm(false)
          if (blocker.state === 'blocked') blocker.proceed()
          else navigate(-1)
        }}
        onClose={() => {
          setShowBackConfirm(false)
          if (blocker.state === 'blocked') blocker.reset()
        }}
      />
    </div>
  )
}

function AssetSlot({
  label,
  src,
  onUpload,
  onRemove,
}: {
  label: string
  src: string | null
  onUpload: (f: File) => void
  onRemove: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <div>
      <div
        onClick={() => {
          if (!src) inputRef.current?.click()
        }}
        className={`relative aspect-square rounded-2xl bg-slate-50 border-2 border-dashed flex items-center justify-center overflow-hidden ${src ? 'border-slate-200' : 'border-slate-200 hover:border-brand-300 cursor-pointer'}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) {
              const validTypes = ['image/jpeg', 'image/png', 'image/webp']
              if (!validTypes.includes(f.type)) {
                alert('Please upload a valid image format (JPEG, PNG, or WEBP).')
                return
              }
              if (f.size > 5 * 1024 * 1024) {
                alert('File size exceeds the 5MB limit. Please choose a smaller file.')
                return
              }
              onUpload(f)
            }
          }}
        />
        {src ? (
          <>
            <img src={src} alt={label} className="w-full h-full object-contain p-3" />
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
          <span className="text-xs text-slate-400 text-center px-2 flex flex-col gap-0.5">
            <span className="font-medium text-slate-500">Click to upload</span>
            <span className="text-[10px]">JPEG, PNG, WEBP</span>
            <span className="text-[10px] font-medium text-slate-400/80 mt-0.5">Max 5MB</span>
          </span>
        )}
      </div>
      <div className="text-xs font-medium text-slate-600 text-center mt-2">{label}</div>
    </div>
  )
}
