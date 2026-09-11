import { useState, useEffect } from 'react'

/**
 * Shared logo hook.
 *
 * Uses a two-tier strategy:
 *  1. PUBLIC  — /api/auth/branding  (no token needed → works on Login page)
 *  2. PRIVATE — /api/organization   (full profile, used when already logged in)
 *
 * The public endpoint is tried first so the logo always appears on the
 * login screen without needing authentication.
 */

let _cached: string | null | undefined = undefined // undefined = not fetched yet
const _listeners = new Set<(url: string | null) => void>()
let _fetching = false

function _notify(url: string | null) {
  _cached = url
  _listeners.forEach((fn) => fn(url))
}

function _buildUrl(logoPath: string | null | undefined): string | null {
  return logoPath ? `/branding/${logoPath}?t=${Date.now()}` : null
}

async function _fetchLogo() {
  if (_fetching) return
  _fetching = true
  try {
    // Try the public endpoint first (works before login)
    const res = await fetch('/api/auth/branding')
    if (res.ok) {
      const data = await res.json()
      _notify(_buildUrl(data.logo_path))
      return
    }
  } catch {
    // fall through
  }
  // Fallback: try the authenticated full-profile endpoint
  try {
    const token = sessionStorage.getItem('pixous_auth_token')
    if (token) {
      const res = await fetch('/api/organization', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        _notify(_buildUrl(data.profile?.logo_path))
        return
      }
    }
  } catch {
    // ignore
  }
  _notify(null)
}

export function useLogo(): string | null {

  const [logoUrl, setLogoUrl] = useState<string | null>(
    _cached !== undefined ? _cached : null
  )

  useEffect(() => {
    // Always subscribe — regardless of whether a cached value already exists
    // — so that any later refreshLogo() call (e.g. uploading/removing a logo
    // in Organization Settings) reaches every mounted consumer, not just the
    // handful that happened to mount before the very first fetch resolved.
    // The previous version returned early here whenever `_cached` was
    // already set, which skipped `_listeners.add` entirely — every page or
    // sidebar mounted after that point (a fresh Login visit, navigating into
    // a workspace, ...) was permanently stuck showing whatever logo existed
    // at the time it first mounted.
    _listeners.add(setLogoUrl)

    if (_cached !== undefined) {
      setLogoUrl(_cached)
    } else if (!_fetching) {
      _fetchLogo()
    }

    return () => {
      _listeners.delete(setLogoUrl)
    }
  }, [])

  return logoUrl
}

/** Call after a successful logo upload/remove to refresh all components instantly. */
export function refreshLogo(logoPath: string | null) {
  _fetching = false
  _cached = undefined
  _notify(_buildUrl(logoPath))
}
