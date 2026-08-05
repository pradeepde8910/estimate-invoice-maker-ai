export default function Card({
  title,
  action,
  children,
  className = '',
}: {
  title?: React.ReactNode
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={`bg-white rounded-3xl shadow-card p-5 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          {typeof title === 'string' ? <h3 className="font-semibold text-slate-800">{title}</h3> : title}
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
