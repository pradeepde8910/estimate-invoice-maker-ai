export const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
export const PHONE_RE = /^[6-9]\d{9}$/
export const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/
export const WEBSITE_RE = /^(https?:\/\/)?([\w.-]+)\.([a-z]{2,6})([\/\w .-]*)*\/?$/i
export const UPI_ID_RE = /^[\w.-]{2,256}@[a-zA-Z]{2,64}$/

export function formatGSTIN(val: string): string {
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
