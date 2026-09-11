import { useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { useLogo } from '../hooks/useLogo'
import { useJob, getJobProgressPct } from '../JobContext'


interface NavItem {
  to: string
  label: string
  description?: string
  icon: (props: React.SVGProps<SVGSVGElement>) => JSX.Element
  end?: boolean
}

const ESTIMATION_NAV: NavItem[] = [
  { to: '/estimation', label: 'Dashboard', description: 'Overview of recent estimates & metrics', icon: ChartIcon, end: true },
  { to: '/estimation/new', label: 'New Estimation', description: 'Upload a doc for an AI-generated quote', icon: PlusIcon },
  { to: '/estimation/list', label: 'Estimations', description: 'Browse and manage all AI estimates', icon: ListIcon },
  { to: '/estimation/rate-card', label: 'Rate Card', description: 'Configure standard hourly billing rates', icon: TagIcon },
  { to: '/estimation/resource-catalog', label: 'Resource Catalog', description: 'Manage team skill profiles and roles', icon: LayersIcon },
  { to: '/estimation/organization', label: 'Organization Settings', description: 'Company profile and branding', icon: BuildingIcon },
]

const INVOICE_NAV: NavItem[] = [
  { to: '/invoice', label: 'Projects & Invoices', description: 'Track ongoing projects and raise bills', icon: ChartIcon, end: true },
  { to: '/invoice/export', label: 'Export Center', description: 'Download financial data as CSV/Excel', icon: DownloadIcon },
  { to: '/invoice/classifications', label: 'Billing Classifications', description: 'Manage HSN/SAC codes and tax rates', icon: TagIcon },
  { to: '/invoice/organization', label: 'Organization Settings', description: 'Company profile and branding', icon: BuildingIcon },
]

export default function WorkspaceSidebar({
  workspace,
  open = false,
  onClose,
}: {
  workspace: 'estimation' | 'invoice'
  /** Whether the off-canvas drawer is open on mobile/tablet (<lg). Ignored at lg+, where the sidebar is always visible inline. */
  open?: boolean
  /** Called to dismiss the drawer — on backdrop click, Escape, or after a nav link is followed. */
  onClose?: () => void
}) {
  const nav = workspace === 'estimation' ? ESTIMATION_NAV : INVOICE_NAV
  const label = workspace === 'estimation' ? 'Estimation Workspace' : 'Invoice Workspace'
  const logoUrl = useLogo()
  const { job, setJobId } = useJob()
  const jobIsActive = job?.status === 'queued' || job?.status === 'running'
  const jobProgressPct = getJobProgressPct(job)

  // Mobile/tablet drawer polish: Escape dismisses it, and background content
  // can't scroll underneath the open overlay. Guarded to <lg (matching the
  // `lg:` breakpoint this drawer itself uses) so a window resized past that
  // width — e.g. rotating a tablet, or a desktop user shrinking the window
  // to test — never leaves body scroll stuck locked once the sidebar goes
  // back to being permanently visible instead of an overlay.
  useEffect(() => {
    if (!open) return
    const mql = window.matchMedia('(max-width: 1023px)')
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose?.()
    }
    const syncScrollLock = () => {
      document.body.style.overflow = mql.matches ? 'hidden' : ''
    }
    document.addEventListener('keydown', handleKey)
    mql.addEventListener('change', syncScrollLock)
    syncScrollLock()
    return () => {
      document.removeEventListener('keydown', handleKey)
      mql.removeEventListener('change', syncScrollLock)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  return (
    <>
      {/* Backdrop — only ever mounted/visible below lg, where the sidebar is an off-canvas drawer. */}
      <div
        onClick={onClose}
        aria-hidden="true"
        className={`print:hidden fixed inset-0 z-40 bg-slate-900/40 transition-opacity lg:hidden ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      />
      <aside
        className={`print:hidden fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-white flex flex-col h-full transform transition-transform duration-200 ease-in-out lg:transform-none lg:static lg:z-auto lg:w-64 lg:shrink-0 lg:h-screen lg:sticky lg:top-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-2 px-6 h-20">
          <div className="flex flex-col gap-1 justify-center min-w-0 flex-1">
            {logoUrl
              ? <img src={logoUrl} alt="Logo" className="h-10 w-auto object-left object-contain" />
              : <span className="text-sm font-bold text-slate-700 leading-tight">Pixous Technologies</span>
            }
            <div className="text-[10px] text-brand-600 leading-none uppercase font-semibold tracking-wider mt-0.5">{label}</div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="lg:hidden shrink-0 w-9 h-9 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 flex items-center justify-center"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <nav className="flex-1 px-4 py-2 space-y-2 overflow-y-auto">
          {nav.map(({ to, label, description, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => {
                // "New Estimation" doubles as the in-progress/result view for
                // whatever job is in JobContext. If that job already finished
                // (or nothing is running), clicking the nav link should always
                // land on a blank form — not the last completed job's results.
                // If a job is still queued/running, leave it alone so the user
                // can keep tracking it.
                if (to === '/estimation/new' && !jobIsActive) {
                  setJobId(null)
                }
                onClose?.()
              }}
              className={({ isActive }) =>
                `flex items-start gap-3 px-4 py-3 rounded-2xl transition-colors ${
                  isActive
                    ? 'bg-brand-100 text-brand-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${isActive ? 'text-brand-600' : 'text-slate-500'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold">{label}</span>
                      {to === '/estimation/new' && jobIsActive && (
                        <span
                          className="shrink-0 text-[10px] font-bold text-brand-700 bg-brand-200/60 rounded-full px-2 py-0.5 tabular-nums uppercase tracking-wide"
                          title="Estimation in progress"
                        >
                          {jobProgressPct}%
                        </span>
                      )}
                    </div>
                    {description && (
                      <div className={`text-xs leading-tight mt-1 ${isActive ? 'text-brand-700/80' : 'text-slate-500'}`}>
                        {description}
                      </div>
                    )}
                  </div>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 pb-4">
          <NavLink
            to="/"
            onClick={() => onClose?.()}
            className="flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
          >
            <HomeIcon className="w-5 h-5 shrink-0" />
            Back to Home
          </NavLink>
        </div>
      </aside>
    </>
  )
}

function HomeIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="M3 11.5 12 4l9 7.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 9.5V20h14V9.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function PlusIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" strokeLinecap="round" />
    </svg>
  )
}
function ListIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" strokeLinejoin="round" />
      <path d="M9 8h6M9 12h6M9 16h3" strokeLinecap="round" />
    </svg>
  )
}
function DownloadIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="M12 4v11m0 0-4-4m4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 18v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function TagIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="m11 3 8 8-7 7-8-8V4h6Z" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  )
}
function ChartIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="M4 20V10M12 20V4M20 20v-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function BuildingIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <rect x="4" y="3" width="16" height="18" rx="1.5" />
      <path d="M9 7h1M14 7h1M9 11h1M14 11h1M9 15h1M14 15h1M10 21v-4h4v4" strokeLinecap="round" />
    </svg>
  )
}
function LayersIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" strokeLinejoin="round" />
      <path d="m3 13 9 5 9-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

