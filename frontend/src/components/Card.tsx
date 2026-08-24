export default function Card({
  title,
  action,
  children,
  className = '',
  onClick,
}: {
  title?: React.ReactNode
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div className={`bg-white rounded-3xl shadow-sm border border-slate-100/60 p-6 min-w-0 ${className}`} onClick={onClick}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-5">
          {typeof title === 'string' ? <h3 className="text-base font-semibold tracking-tight text-slate-800">{title}</h3> : title}
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
