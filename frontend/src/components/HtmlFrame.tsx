import { useRef, useState } from 'react'

/** Renders a full, self-styled HTML document (like the invoice template) in
 * an isolated iframe so its <style> block can't leak into/collide with the
 * app's own Tailwind styles, auto-resized to fit its content. */
export default function HtmlFrame({ html }: { html: string }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(600)

  function handleLoad() {
    const doc = ref.current?.contentDocument
    if (doc?.documentElement) {
      setHeight(doc.documentElement.scrollHeight + 20)
    }
  }

  return (
    <iframe
      ref={ref}
      srcDoc={html}
      onLoad={handleLoad}
      title="Invoice preview"
      style={{ height, width: '100%', border: 'none', display: 'block' }}
    />
  )
}
