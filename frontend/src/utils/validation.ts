export const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
export const PHONE_RE = /^[6-9]\d{9}$/
export const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/
export const WEBSITE_RE = /^(https?:\/\/)?([\w.-]+)\.([a-z]{2,6})([\/\w .-]*)*\/?$/i
export const UPI_ID_RE = /^[\w.-]{2,256}@[a-zA-Z]{2,64}$/

// Cosmetic-only: uppercase, strip anything that isn't alphanumeric, cap at 15
// characters. Deliberately does NOT enforce per-position character classes
// (digit here, letter there) while typing — an earlier version did, and a
// single character that didn't fit its expected slot was silently dropped
// instead of just being left for the field's real validator (GSTIN_RE) to
// catch, which made correcting or pasting a GSTIN feel like typing got
// "stuck" partway through. GSTIN_RE (checked on submit wherever this is
// used) is the sole authority on whether the final value is a valid GSTIN.
export function formatGSTIN(val: string): string {
  return val.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 15)
}

export function formatPhone(val: string): string {
  let cleaned = val
  if (cleaned.startsWith('+91')) {
     cleaned = cleaned.slice(3)
  } else if (cleaned.startsWith('91') && cleaned.replace(/\D/g, '').length > 10) {
     cleaned = cleaned.slice(2)
  }
  return cleaned.replace(/\D/g, '').slice(0, 10)
}

export function uiFormatPhone(val: string): string {
  const digits = formatPhone(val)
  if (digits.length === 0) return ''
  if (digits.length > 5) return '+91 ' + digits.slice(0, 5) + ' ' + digits.slice(5)
  return '+91 ' + digits
}
