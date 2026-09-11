import Spinner from './Spinner'

/** Shown briefly while a lazy-loaded route chunk is being fetched. */
export default function PageFallback() {
  return (
    <div className="flex-1 min-h-screen flex items-center justify-center bg-transparent">
      <Spinner className="h-8 w-8 text-brand-500" />
    </div>
  )
}
