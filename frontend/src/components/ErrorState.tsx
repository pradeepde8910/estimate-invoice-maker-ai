/**
 * Persistent, muted "couldn't load this" placeholder — for the rare case
 * where a fetch failure leaves a section with nothing else to show, so a
 * transient toast alone (see main.tsx's <Toaster/>) would vanish and leave
 * a blank page with no clue why. Action failures (save/delete/download/...)
 * should use `toast.error(...)` instead of this — this is only for "there is
 * genuinely nothing here because the load failed."
 */
export default function ErrorState({ message, className = '' }: { message: string; className?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center gap-2 py-10 text-slate-400 ${className}`}>
      <svg className="w-8 h-8 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v5" />
        <path d="M12 16h.01" />
      </svg>
      <p className="text-sm">{message}</p>
    </div>
  )
}
