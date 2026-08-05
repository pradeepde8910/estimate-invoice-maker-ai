import { useState } from 'react'
import { useJob } from '../JobContext'

export default function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { notifications, clearNotifications } = useJob()
  const [open, setOpen] = useState(false)

  return (
    <header className="flex items-center justify-between gap-4 px-8 h-20 bg-transparent sticky top-0 z-10">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold text-slate-900 truncate">{title}</h1>
        {subtitle && <p className="text-sm text-slate-400 mt-0.5 truncate">{subtitle}</p>}
      </div>

      <div className="relative shrink-0">
        <button
          onClick={() => setOpen((o) => !o)}
          className="relative w-11 h-11 rounded-full bg-white shadow-card flex items-center justify-center text-slate-500 hover:bg-slate-50"
        >
          🔔
          {notifications.length > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-coral-500 text-white text-[11px] flex items-center justify-center font-semibold">
              {notifications.length}
            </span>
          )}
        </button>
        {open && (
          <div className="absolute right-0 mt-2 w-80 bg-white rounded-3xl shadow-lg p-3 z-20">
            <div className="flex items-center justify-between mb-2 px-1">
              <span className="font-semibold text-sm text-slate-700">Notifications</span>
              {notifications.length > 0 && (
                <button onClick={clearNotifications} className="text-xs text-brand-600 hover:underline">
                  Clear
                </button>
              )}
            </div>
            {notifications.length === 0 ? (
              <p className="text-sm text-slate-400 py-4 text-center">You're all caught up.</p>
            ) : (
              <ul className="space-y-2 max-h-64 overflow-y-auto">
                {notifications.map((n, i) => (
                  <li key={i} className="text-sm text-slate-600 bg-slate-50 rounded-2xl px-3 py-2">
                    {n}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
