const TONES = {
  mint: {
    bg: 'bg-gradient-to-br from-teal-50/50 via-white to-white border border-teal-100/30',
    blob: 'bg-teal-100/40',
    text: 'text-teal-700',
  },
  coral: {
    bg: 'bg-gradient-to-br from-rose-50/50 via-white to-white border border-rose-100/30',
    blob: 'bg-rose-100/40',
    text: 'text-rose-700',
  },
}

export default function HeroStat({
  label,
  value,
  sub,
  tone = 'mint',
}: {
  label: string
  value: React.ReactNode
  sub?: string
  tone?: 'mint' | 'coral'
}) {
  const t = TONES[tone]
  return (
    <div className={`relative overflow-hidden rounded-3xl ${t.bg} shadow-card p-5 h-full min-w-0`}>
      <div className={`absolute -right-6 -top-8 w-28 h-28 rounded-full blur-2xl ${t.blob}`} />
      <div className="relative min-w-0">
        <div className="text-sm font-medium text-slate-500">{label}</div>
        <div
          className={`text-3xl font-bold tracking-tight mt-2 truncate ${t.text}`}
          title={typeof value === 'string' ? value : undefined}
        >
          {value}
        </div>
        {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
      </div>
    </div>
  )
}
