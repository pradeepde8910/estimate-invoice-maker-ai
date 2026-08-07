import { useEffect, useId, useRef, useState } from 'react'
import mermaid from 'mermaid'

let initialized = false
function ensureInit() {
  if (initialized) return
  mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict', suppressErrorRendering: true })
  initialized = true
}

export default function Mermaid({ chart }: { chart: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '')
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ensureInit()
    let cancelled = false
    setError(null)
    const renderId = `mermaid-${id}`
    mermaid
      .render(renderId, chart.trim())
      .then(({ svg }) => {
        if (!cancelled && containerRef.current) containerRef.current.innerHTML = svg
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        // Clean up stranded error SVGs that Mermaid injects into the body on failure
        const dNode = document.getElementById(`d${renderId}`)
        if (dNode) dNode.remove()
        const node = document.getElementById(renderId)
        if (node) node.remove()
      })
    return () => {
      cancelled = true
    }
  }, [chart, id])

  if (error) {
    return (
      <div className="text-xs text-rose-600 bg-rose-50 rounded-lg px-3 py-2 my-4">
        Couldn't render diagram: {error}
        <pre className="mt-2 whitespace-pre-wrap text-slate-500">{chart}</pre>
      </div>
    )
  }

  return <div ref={containerRef} className="my-4 flex justify-center overflow-x-auto [&_svg]:max-w-full" />
}
