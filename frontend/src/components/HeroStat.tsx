const TONES = {
  mint: {
    bg: 'bg-gradient-to-br from-brand-50 via-white to-white',
    blob: 'bg-brand-200/70',
    text: 'text-brand-700',
  },
  coral: {
    bg: 'bg-gradient-to-br from-coral-50 via-white to-white',
    blob: 'bg-coral-200/60',
    text: 'text-coral-600',
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
    <div className={`relative overflow-hidden rounded-3xl ${t.bg} shadow-card p-5 h-full`}>
      <div className={`absolute -right-6 -top-8 w-28 h-28 rounded-full blur-2xl ${t.blob}`} />
      <div className="relative">
        <div className="text-sm font-medium text-slate-500">{label}</div>
        <div className={`text-3xl font-bold mt-2 ${t.text}`}>{value}</div>
        {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
      </div>
    </div>
  )
}
