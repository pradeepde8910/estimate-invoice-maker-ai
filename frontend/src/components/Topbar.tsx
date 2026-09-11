import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOpenSidebar } from '../SidebarMenuContext'
import { logout } from '../api/client'
import ConfirmModal from './ConfirmModal'

export default function Topbar({ title, subtitle, showBack = false, onBack, children, showAccount = true }: { title: string; subtitle?: string; showBack?: boolean; onBack?: () => void; children?: React.ReactNode; showAccount?: boolean }) {
  const navigate = useNavigate()
  const openSidebar = useOpenSidebar()
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  return (
    <header className="print:hidden flex items-center justify-between gap-4 px-4 sm:px-8 h-20 bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
      <div className="flex items-center gap-4 min-w-0">
        {openSidebar && (
          <button
            onClick={openSidebar}
            aria-label="Open menu"
            className="lg:hidden flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-100 hover:border-slate-300 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
        )}
        {showBack && (
          <button
            onClick={() => onBack ? onBack() : navigate(-1)}
            className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-100 hover:border-slate-300 transition-colors"
            title="Go back"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
            </svg>
          </button>
        )}
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 truncate">{title}</h1>
          {subtitle && <p className="text-sm text-slate-500 mt-0.5 truncate">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {children}
        {showAccount && (
          <div className="flex items-center gap-2.5 bg-slate-50 border border-slate-200 rounded-2xl pl-3 pr-2 py-1.5 shrink-0">
            <div className="hidden sm:block text-right leading-tight">
              <div className="text-xs font-semibold text-slate-700 whitespace-nowrap">Pixous Admin</div>
              <div className="text-[10px] text-slate-400 whitespace-nowrap">Administrator</div>
            </div>
            <div title="Pixous Admin — Administrator" className="w-9 h-9 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
              <AdminIcon className="w-5 h-5" />
            </div>
            <div className="w-px self-stretch bg-slate-200" />
            <button
              onClick={() => setShowLogoutConfirm(true)}
              className="w-8 h-8 rounded-full text-slate-400 hover:bg-coral-50 hover:text-coral-500 flex items-center justify-center transition-colors shrink-0"
              title="Log Out"
            >
              <LogoutIcon className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {showAccount && (
        <ConfirmModal
          isOpen={showLogoutConfirm}
          title="Log Out"
          message="Are you sure you want to log out of your session?"
          confirmText="Log Out"
          onConfirm={logout}
          onCancel={() => setShowLogoutConfirm(false)}
        />
      )}
    </header>
  )
}

function LogoutIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function AdminIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4.4 3.6-7 8-7s8 2.6 8 7" strokeLinecap="round" />
    </svg>
  )
}
