import { useEffect, useRef, useState } from 'react'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import BackLink from '../components/BackLink'
import { getOrganization, updateOrganization, uploadOrganizationAsset, deleteOrganizationAsset } from '../api/client'
import ConfirmModal from '../components/ConfirmModal'
import type { OrganizationProfile } from '../api/types'
import { refreshLogo } from '../hooks/useLogo'

type AssetSlotKey = 'logo' | 'signature' | 'seal'

const FIELD_ROWS: { key: keyof OrganizationProfile; label: string; placeholder?: string; span?: boolean; multiline?: boolean }[] = [
  { key: 'name', label: 'Company Name', span: true },
  { key: 'tagline', label: 'Tagline', placeholder: 'e.g. Strategize · Amplify · Transform', span: true },
  { key: 'address', label: 'Address', span: true, multiline: true },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'website', label: 'Website' },
  { key: 'gstin', label: 'GSTIN' },
  { key: 'registration_number', label: 'Registration Number' },
  { key: 'certifications', label: 'Certifications', placeholder: 'e.g. ISO 9001:2015 · CMMI Level 3', span: true, multiline: true },
  { key: 'signatory_name', label: 'Authorized Signatory Name' },
  { key: 'signatory_title', label: 'Signatory Title' },
  { key: 'invoice_terms', label: 'Invoice Terms & Conditions', placeholder: 'Enter terms, one per line', span: true, multiline: true },
]

const BANK_FIELD_ROWS: { key: keyof OrganizationProfile; label: string }[] = [
  { key: 'bank_name', label: 'Bank Name' },
  { key: 'bank_account_number', label: 'Account Number' },
  { key: 'bank_ifsc', label: 'IFSC Code' },
  { key: 'bank_branch', label: 'Branch' },
]

export default function OrganizationSettings() {
  const [profile, setProfile] = useState<OrganizationProfile | null>(null)
  const [savedProfile, setSavedProfile] = useState<OrganizationProfile | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [bankExpanded, setBankExpanded] = useState(false)
  const [removeConfirm, setRemoveConfirm] = useState<AssetSlotKey | null>(null)

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
  }

  async function handleAssetUpload(slot: AssetSlotKey, file: File) {
    setError(null)
    try {
      const r = await uploadOrganizationAsset(slot, file)
      const newPath = (r.profile as any)[`${slot}_path`]
      setProfile((prev) => prev ? { ...prev, [`${slot}_path`]: newPath } : r.profile)
      if (slot === 'logo') refreshLogo(newPath)
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
                    <label className="text-xs font-medium text-slate-500">{f.label}</label>
                    {f.multiline ? (
                      <textarea
                        value={(profile[f.key] as string) || ''}
                        placeholder={f.placeholder}
                        rows={3}
                        onChange={(e) => {
                          setProfile({ ...profile, [f.key]: e.target.value })
                          setSaved(false)
                          setIsDirty(true)
                        }}
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300 resize-none"
                      />
                    ) : (
                      <input
                        value={(profile[f.key] as string) || ''}
                        placeholder={f.placeholder}
                        onChange={(e) => {
                          setProfile({ ...profile, [f.key]: e.target.value })
                          setSaved(false)
                          setIsDirty(true)
                        }}
                        className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                      />
                    )}
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
        onClick={() => inputRef.current?.click()}
        className="relative aspect-square rounded-2xl bg-slate-50 border-2 border-dashed border-slate-200 hover:border-brand-300 cursor-pointer flex items-center justify-center overflow-hidden"
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
              title={`Remove ${label}`}
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
