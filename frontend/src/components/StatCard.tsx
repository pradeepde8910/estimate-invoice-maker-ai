export default function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="text-left px-2 min-w-0">
      <div className="text-sm font-medium text-slate-500">{label}</div>
      <div className="text-3xl font-bold tracking-tight text-indigo-600 truncate mt-2" title={typeof value === 'string' ? value : undefined}>
        {value}
      </div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  )
}
