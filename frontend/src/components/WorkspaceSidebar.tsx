import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { logout } from '../api/client'
import ConfirmModal from './ConfirmModal'
import { useLogo } from '../hooks/useLogo'


interface NavItem {
  to: string
  label: string
  icon: (props: React.SVGProps<SVGSVGElement>) => JSX.Element
  end?: boolean
}

const ESTIMATION_NAV: NavItem[] = [
  { to: '/estimation', label: 'Dashboard', icon: ChartIcon, end: true },
  { to: '/estimation/new', label: 'New Estimation', icon: PlusIcon },
  { to: '/estimation/list', label: 'Estimations', icon: ListIcon },
  { to: '/rate-card', label: 'Rate Card', icon: TagIcon },
  { to: '/organization', label: 'Organization Settings', icon: BuildingIcon },
]

const INVOICE_NAV: NavItem[] = [
  { to: '/invoice', label: 'Dashboard', icon: ChartIcon, end: true },
  { to: '/invoice/new', label: 'New Invoice', icon: PlusIcon },
  { to: '/invoice/list', label: 'Invoice History', icon: ListIcon },
  { to: '/organization', label: 'Organization Settings', icon: BuildingIcon },
]

export default function WorkspaceSidebar({ workspace }: { workspace: 'estimation' | 'invoice' }) {
  const nav = workspace === 'estimation' ? ESTIMATION_NAV : INVOICE_NAV
  const label = workspace === 'estimation' ? 'Estimation Workspace' : 'Invoice Workspace'
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const logoUrl = useLogo()

  return (
    <aside className="w-64 shrink-0 bg-white flex flex-col h-screen sticky top-0">
      <div className="flex flex-col gap-1 px-6 h-20 justify-center">
        {logoUrl
          ? <img src={logoUrl} alt="Logo" className="h-10 w-auto object-left object-contain" />
          : <span className="text-sm font-bold text-slate-700 leading-tight">Pixous Technologies</span>
        }
        <div className="text-[10px] text-black leading-none uppercase font-semibold tracking-wider mt-0.5">{label}</div>
      </div>

      <nav className="flex-1 px-4 py-2 space-y-1.5">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-100 text-brand-700'
                  : 'text-black hover:bg-slate-50 hover:text-black'
              }`
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 pb-2">
        <NavLink
          to="/"
          className="flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-medium text-black hover:bg-slate-50 hover:text-black"
        >
          <HomeIcon className="w-5 h-5 shrink-0" />
          Back to Home
        </NavLink>
        <button
          onClick={() => setShowLogoutConfirm(true)}
          className="w-full flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-medium text-coral-500 hover:bg-coral-50 hover:text-coral-600 transition-colors mt-1"
        >
          <LogoutIcon className="w-5 h-5 shrink-0" />
          Log Out
        </button>
        <ConfirmModal
          isOpen={showLogoutConfirm}
          title="Log Out"
          message="Are you sure you want to log out of your session?"
          confirmText="Log Out"
          onConfirm={logout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      </div>

      <div className="m-4 rounded-2xl bg-slate-50 p-3 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
          PA
        </div>
        <div className="text-sm min-w-0">
          <div className="font-medium text-slate-800 leading-tight truncate">Pixous Admin</div>
          <div className="text-xs text-slate-400 leading-tight truncate">Administrator</div>
        </div>
      </div>
    </aside>
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
function LogoutIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

