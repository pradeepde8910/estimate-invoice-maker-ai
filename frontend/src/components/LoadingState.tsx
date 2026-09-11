import Spinner from './Spinner'

/** Centered spinner + label for a page/section/table waiting on data — the
 * consistent replacement for a bare "Loading…" text node with no animation.
 * `className` fully replaces the default vertical padding (`py-12`) rather
 * than being appended alongside it, so a tighter caller (e.g. a table row)
 * can pass `"py-6"` without both classes fighting over the same property. */
export default function LoadingState({ label = 'Loading…', className = 'py-12' }: { label?: string; className?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 text-sm text-slate-400 ${className}`}>
      <Spinner className="h-6 w-6 text-brand-400" />
      <span>{label}</span>
    </div>
  )
}
