import { useEffect, useRef, useState } from 'react'
import Topbar from '../components/Topbar'
import Card from '../components/Card'
import BackLink from '../components/BackLink'
import { getOrganization, updateOrganization, uploadOrganizationAsset } from '../api/client'
import type { OrganizationProfile } from '../api/types'

const FIELD_ROWS: { key: keyof OrganizationProfile; label: string; placeholder?: string; span?: boolean }[] = [
  { key: 'name', label: 'Company Name', span: true },
  { key: 'tagline', label: 'Tagline', placeholder: 'e.g. Strategize · Amplify · Transform', span: true },
  { key: 'address', label: 'Address', span: true },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'website', label: 'Website' },
  { key: 'gstin', label: 'GSTIN' },
  { key: 'registration_number', label: 'Registration Number' },
  { key: 'certifications', label: 'Certifications', placeholder: 'e.g. ISO 9001:2015 · CMMI Level 3', span: true },
  { key: 'signatory_name', label: 'Authorized Signatory Name' },
  { key: 'signatory_title', label: 'Signatory Title' },
]

const BANK_FIELD_ROWS: { key: keyof OrganizationProfile; label: string }[] = [
  { key: 'bank_name', label: 'Bank Name' },
  { key: 'bank_account_number', label: 'Account Number' },
  { key: 'bank_ifsc', label: 'IFSC Code' },
  { key: 'bank_branch', label: 'Branch' },
]

export default function OrganizationSettings() {
  const [profile, setProfile] = useState<OrganizationProfile | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getOrganization()
      .then((r) => setProfile(r.profile))
      .catch((e) => setError(e.message))
  }, [])

  async function save() {
    if (!profile) return
    setSaving(true)
    setError(null)
    try {
      const { logo_path, signature_path, seal_path, ...fields } = profile
      const r = await updateOrganization(fields)
      setProfile({ ...r.profile, logo_path, signature_path, seal_path })
      setSaved(true)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleAssetUpload(slot: 'logo' | 'signature' | 'seal', file: File) {
    setError(null)
    try {
      const r = await uploadOrganizationAsset(slot, file)
      setProfile(r.profile)
    } catch (e: any) {
      setError(e.message)
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
                  {saved && <span className="text-xs text-brand-600 font-medium">Saved ✓</span>}
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
                    <input
                      value={(profile[f.key] as string) || ''}
                      placeholder={f.placeholder}
                      onChange={(e) => {
                        setProfile({ ...profile, [f.key]: e.target.value })
                        setSaved(false)
                      }}
                      className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                    />
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Bank Details" action={<span className="text-xs text-slate-400">Shown on invoices, when filled in</span>}>
              <div className="grid grid-cols-2 gap-4">
                {BANK_FIELD_ROWS.map((f) => (
                  <div key={f.key}>
                    <label className="text-xs font-medium text-slate-500">{f.label}</label>
                    <input
                      value={(profile[f.key] as string) || ''}
                      onChange={(e) => {
                        setProfile({ ...profile, [f.key]: e.target.value })
                        setSaved(false)
                      }}
                      className="mt-1 w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
                    />
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Branding Assets">
              <div className="grid grid-cols-3 gap-5">
                <AssetSlot
                  label="Logo"
                  path={profile.logo_path}
                  onUpload={(f) => handleAssetUpload('logo', f)}
                />
                <AssetSlot
                  label="Signature"
                  path={profile.signature_path}
                  onUpload={(f) => handleAssetUpload('signature', f)}
                />
                <AssetSlot
                  label="Company Seal"
                  path={profile.seal_path}
                  onUpload={(f) => handleAssetUpload('seal', f)}
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
    </div>
  )
}

function AssetSlot({ label, path, onUpload }: { label: string; path: string | null; onUpload: (f: File) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <div>
      <div
        onClick={() => inputRef.current?.click()}
        className="aspect-square rounded-2xl bg-slate-50 border-2 border-dashed border-slate-200 hover:border-brand-300 cursor-pointer flex items-center justify-center overflow-hidden"
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
          <img src={`/branding/${path}?t=${Date.now()}`} alt={label} className="w-full h-full object-contain p-3" />
        ) : (
          <span className="text-xs text-slate-400 text-center px-2">Click to upload</span>
        )}
      </div>
      <div className="text-xs font-medium text-slate-600 text-center mt-2">{label}</div>
    </div>
  )
}
