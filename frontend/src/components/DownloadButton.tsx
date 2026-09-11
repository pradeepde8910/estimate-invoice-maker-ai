import { useState } from 'react'

type DownloadState = 'idle' | 'loading' | 'done'

/**
 * Button that gives explicit feedback for a download action instead of going
 * silent between click and the browser's save prompt. Features premium micro-animations
 * like a shimmering background, bouncing arrow, and success ping.
 * Falls back to the base `label` if `onDownload` rejects.
 */
export default function DownloadButton({
  onDownload,
  label,
  loadingLabel = 'Preparing…',
  doneLabel = 'Downloaded!',
  className = '',
  disabled = false,
}: {
  onDownload: () => Promise<void> | void
  label: React.ReactNode
  loadingLabel?: string
  doneLabel?: string
  className?: string
  disabled?: boolean
}) {
  const [state, setState] = useState<DownloadState>('idle')

  async function handleClick() {
    if (state === 'loading') return
    setState('loading')
    try {
      await onDownload()
      setState('done')
      setTimeout(() => setState('idle'), 2500)
    } catch {
      setState('idle')
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled || state === 'loading'}
      className={`relative inline-flex items-center justify-center gap-2 overflow-hidden transition-all duration-300 disabled:cursor-wait ${
        state === 'loading' ? 'bg-brand-50 text-brand-700 border-brand-200' : ''
      } ${
        state === 'done' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : ''
      } ${className}`}
    >
      {/* Premium Shimmer effect background during loading */}
      {state === 'loading' && (
        <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/60 to-transparent" />
      )}

      {state === 'loading' ? (
        <>
          <span className="relative flex h-5 w-5 items-center justify-center shrink-0">
            {/* The base tray */}
            <svg className="absolute inset-0 h-5 w-5 text-brand-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" opacity="0.4" />
            </svg>
            {/* The bouncing document/arrow */}
            <svg className="absolute inset-0 h-5 w-5 text-brand-600 animate-bounce" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 11l5 5 5-5" />
              <path d="M12 4v12" />
            </svg>
          </span>
          <span className="font-medium animate-pulse">{loadingLabel}</span>
        </>
      ) : state === 'done' ? (
        <>
          <span className="relative flex h-5 w-5 items-center justify-center shrink-0">
            {/* Success Burst effect */}
            <div className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-30"></div>
            <svg viewBox="0 0 24 24" className="h-5 w-5 animate-pop-in text-emerald-600" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 6L9 17l-5-5" />
            </svg>
          </span>
          <span className="font-medium">{doneLabel}</span>
        </>
      ) : (
        label
      )}
    </button>
  )
}
