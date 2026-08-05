const ICONS = ['📄', '⧉', '📊', '🧮', '🌐', '📃', '📋', '✅']

export default function Stepper({
  steps,
  stepIndex,
  failed,
}: {
  steps: string[]
  stepIndex: number
  failed?: boolean
}) {
  return (
    <div className="flex items-start overflow-x-auto pb-2">
      {steps.map((label, i) => {
        const isComplete = i < stepIndex || (i === stepIndex && stepIndex === steps.length - 1 && !failed)
        const isCurrent = i === stepIndex && !isComplete
        const isFailedHere = failed && i === stepIndex
        return (
          <div key={label} className="flex items-start flex-1 min-w-[64px]">
            <div className="flex flex-col items-center flex-1">
              <div
                className={`w-10 h-10 rounded-full border-2 flex items-center justify-center text-sm transition-colors ${
                  isFailedHere
                    ? 'border-coral-400 bg-coral-50 text-coral-500'
                    : isComplete
                    ? 'border-brand-400 bg-brand-50 text-brand-600'
                    : isCurrent
                    ? 'border-brand-500 bg-brand-50 text-brand-600 animate-pulse'
                    : 'border-slate-200 bg-white text-slate-300'
                }`}
              >
                {isFailedHere ? '⚠️' : ICONS[i] ?? '•'}
              </div>
              <div className="mt-2 text-[11px] font-medium text-slate-600 text-center px-0.5 leading-tight">{label}</div>
              <div
                className={`text-[10px] font-medium mt-0.5 ${
                  isFailedHere
                    ? 'text-coral-500'
                    : isComplete
                    ? 'text-brand-600'
                    : isCurrent
                    ? 'text-brand-600'
                    : 'text-slate-300'
                }`}
              >
                {isFailedHere ? 'Failed' : isComplete ? 'Complete' : isCurrent ? 'In Progress' : 'Pending'}
              </div>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`h-0.5 flex-1 mt-5 ${i < stepIndex ? 'bg-brand-300' : 'bg-slate-200'}`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
