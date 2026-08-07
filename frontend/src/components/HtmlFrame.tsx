import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'

export interface HtmlFrameHandle {
  /** Reads back the current (possibly hand-edited) document as an HTML string. */
  getHtml: () => string
}

/** Renders a full, self-styled HTML document (like the invoice template) in
 * an isolated iframe so its <style> block can't leak into/collide with the
 * app's own Tailwind styles, auto-resized to fit its content.
 *
 * When `editable` is true, the rendered document itself becomes directly
 * editable (via the iframe's native designMode) — the user clicks into the
 * invoice and types on the real layout, no raw HTML ever shown. */
const HtmlFrame = forwardRef<HtmlFrameHandle, { html: string; editable?: boolean }>(
  ({ html, editable = false }, ref) => {
    const iframeRef = useRef<HTMLIFrameElement>(null)
    const [height, setHeight] = useState(600)

    function applyEditable() {
      const doc = iframeRef.current?.contentDocument
      if (doc) doc.designMode = editable ? 'on' : 'off'
    }

    function handleLoad() {
      const doc = iframeRef.current?.contentDocument
      if (doc?.documentElement) {
        setHeight(doc.documentElement.scrollHeight + 20)
      }
      applyEditable()
    }

    // Toggling `editable` alone (without the srcDoc changing) doesn't refire
    // onLoad, so flip designMode on the already-loaded document directly.
    useEffect(applyEditable, [editable])

    useImperativeHandle(ref, () => ({
      getHtml: () => {
        const doc = iframeRef.current?.contentDocument
        if (!doc?.documentElement) return html
        return `<!DOCTYPE html>\n${doc.documentElement.outerHTML}`
      },
    }))

    return (
      <iframe
        ref={iframeRef}
        srcDoc={html}
        onLoad={handleLoad}
        title="Invoice preview"
        // allow-same-origin (but NOT allow-scripts): the parent still needs
        // same-origin access to contentDocument for getHtml()/designMode
        // editing, but the invoice template never needs to run JavaScript,
        // so script execution stays fully disabled. That means any <script>
        // or on* handler that ends up in server-stored invoice HTML (e.g.
        // via manual edits) simply never runs - it can't reach
        // window.parent/localStorage regardless of what content makes it
        // into invoice_html.
        sandbox="allow-same-origin"
        style={{
          height,
          width: '100%',
          border: 'none',
          display: 'block',
          outline: editable ? '2px dashed #93c5fd' : 'none',
          outlineOffset: '-2px',
        }}
      />
    )
  }
)

export default HtmlFrame
