export default function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="flex items-center justify-between gap-4 px-8 h-20 bg-white border-b border-slate-200 shadow-sm sticky top-0 z-50">
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-black truncate">{title}</h1>
        {subtitle && <p className="text-sm text-black mt-0.5 truncate">{subtitle}</p>}
      </div>
    </header>
  )
}
