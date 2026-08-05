export default function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="text-center px-2">
      <div className="text-2xl font-bold text-brand-700">{value}</div>
      <div className="text-sm font-medium text-slate-500 mt-1">{label}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  )
}
