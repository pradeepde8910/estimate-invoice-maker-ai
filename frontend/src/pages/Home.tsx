import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import Topbar from '../components/Topbar'
import { logout } from '../api/client'
import ConfirmModal from '../components/ConfirmModal'
import { useLogo } from '../hooks/useLogo'

export default function Home() {
  const navigate = useNavigate()
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const logoUrl = useLogo()

  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 17) return 'Good afternoon'
    return 'Good evening'
  }

  return (
    <div className="flex-1 min-h-screen bg-transparent">
      <header className="flex items-center justify-between px-8 h-16 border-b border-slate-100 bg-white">
        <div className="flex items-center">
          {logoUrl
            ? <img src={logoUrl} alt="Logo" className="h-8 w-auto object-contain" />
            : <span className="text-sm font-bold text-slate-700">Pixous Technologies</span>
          }
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/estimation/organization')}
            className="w-9 h-9 rounded-full text-slate-400 hover:bg-slate-50 hover:text-slate-600 flex items-center justify-center"
            title="Organization Settings"
          >
            <GearIcon className="w-5 h-5" />
          </button>
          <button
            onClick={() => setShowLogoutConfirm(true)}
            className="w-9 h-9 rounded-full text-slate-400 hover:bg-coral-50 hover:text-coral-500 flex items-center justify-center transition-colors"
            title="Log Out"
          >
            <LogoutIcon className="w-5 h-5" />
          </button>
          <div title="Pixous Admin Profile" className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold text-sm">
            PA
          </div>
        </div>
      </header>

      <Topbar title={`${getGreeting()}, Pixous Admin 👋`} subtitle="What would you like to do today?" />
      <div className="p-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
          <OptionCard
            tone="coral"
            icon="📥"
            title="Estimation Maker"
            description="Upload a requirement document and get an AI-generated cost & timeline estimate for your client."
            cta="Open Estimation Maker"
            onClick={() => navigate('/estimation')}
          />
          <OptionCard
            tone="mint"
            icon="🧾"
            title="Invoice Maker"
            description="Turn a finished estimation into a client-ready invoice — line items, tax, and due date included."
            cta="Open Invoice Maker"
            onClick={() => navigate('/invoice')}
          />
        </div>
      </div>
      <ConfirmModal
        isOpen={showLogoutConfirm}
        title="Log Out"
        message="Are you sure you want to log out of your session?"
        confirmText="Log Out"
        onConfirm={logout}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </div>
  )
}

function OptionCard({
  tone,
  icon,
  title,
  description,
  cta,
  onClick,
}: {
  tone: 'mint' | 'coral'
  icon: string
  title: string
  description: string
  cta: string
  onClick: () => void
}) {
  const bg = tone === 'mint' ? 'from-brand-50 via-white to-white' : 'from-coral-50 via-white to-white'
  const blob = tone === 'mint' ? 'bg-brand-200/70' : 'bg-coral-200/60'
  const button = tone === 'mint' ? 'bg-brand-600 hover:bg-brand-700' : 'bg-coral-500 hover:bg-coral-600'

  return (
    <button
      onClick={onClick}
      className={`relative overflow-hidden text-left rounded-3xl bg-gradient-to-br ${bg} shadow-card p-8 transition-transform hover:-translate-y-0.5`}
    >
      <div className={`absolute -right-10 -top-10 w-40 h-40 rounded-full blur-2xl ${blob}`} />
      <div className="relative">
        <div className="w-14 h-14 rounded-2xl bg-white shadow-card flex items-center justify-center text-2xl mb-5">
          {icon}
        </div>
        <h2 className="text-xl font-semibold tracking-tight text-slate-800">{title}</h2>
        <p className="text-sm text-slate-500 mt-2 leading-relaxed max-w-sm">{description}</p>
        <span className={`inline-block mt-6 text-sm font-medium text-white px-5 py-2.5 rounded-full ${button}`}>
          {cta} →
        </span>
      </div>
    </button>
  )
}

function GearIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1Z" />
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
