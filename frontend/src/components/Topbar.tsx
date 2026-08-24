import { useNavigate } from 'react-router-dom'

export default function Topbar({ title, subtitle, showBack = false, onBack, children }: { title: string; subtitle?: string; showBack?: boolean; onBack?: () => void; children?: React.ReactNode }) {
  const navigate = useNavigate()
  return (
    <header className="flex items-center justify-between gap-4 px-8 h-20 bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
      <div className="flex items-center gap-4 min-w-0">
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
      {children && <div className="flex items-center gap-3">{children}</div>}
    </header>
  )
}
