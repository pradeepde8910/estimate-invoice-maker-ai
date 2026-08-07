import { useEffect, useState } from 'react'
import { getOrganization } from '../api/client'

let _cached: string | null | undefined = undefined // undefined = not fetched yet
const _listeners = new Set<(url: string | null) => void>()

function _notify(url: string | null) {
  _cached = url
  _listeners.forEach((fn) => fn(url))
}

/**
 * Returns the live logo URL (e.g. "/branding/logo.jpg") from the
 * organization profile.  Returns null if no logo is uploaded yet.
 * Results are cached in memory so all components share one network call.
 */
export function useLogo(): string | null {
  const [logoUrl, setLogoUrl] = useState<string | null>(
    _cached !== undefined ? _cached : null
  )

  useEffect(() => {
    if (_cached !== undefined) {
      // Already fetched — use the cache immediately
      setLogoUrl(_cached)
      return
    }

    // Subscribe so we get notified when the fetch completes
    _listeners.add(setLogoUrl)

    // Only the first caller actually fetches
    if (_listeners.size === 1) {
      getOrganization()
        .then(({ profile }) => {
          const path = profile.logo_path
          const url = path ? `/branding/${path}?t=${Date.now()}` : null
          _notify(url)
        })
        .catch(() => _notify(null))
    }

    return () => {
      _listeners.delete(setLogoUrl)
    }
  }, [])

  return logoUrl
}

/** Call this after a successful logo upload to refresh every component. */
export function refreshLogo(logoPath: string | null) {
  const url = logoPath ? `/branding/${logoPath}?t=${Date.now()}` : null
  _cached = undefined // reset cache so next useLogo call re-fetches if needed
  _notify(url)
}
