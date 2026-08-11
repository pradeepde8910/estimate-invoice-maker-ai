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

    const parseNumber = (str: string | null | undefined) => {
      if (!str) return 0
      const val = parseFloat(str.replace(/[^0-9.-]+/g, ''))
      return isNaN(val) ? 0 : val
    }

    const formatINR = (num: number) => {
      return '₹' + num.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    }

    const handleInvoiceInput = (e: Event) => {
      const doc = iframeRef.current?.contentDocument
      if (!doc) return
      
      const target = e.target as HTMLElement
      const rows = doc.querySelectorAll('.items-table tbody tr')
      let subtotal = 0
      let totalGst = 0

      rows.forEach((row) => {
        const cells = row.querySelectorAll('td')
        if (cells.length === 6) {
          const qtyCell = cells[2] as HTMLElement
          const rateCell = cells[3] as HTMLElement
          const gstCell = cells[4] as HTMLElement
          const amountCell = cells[5] as HTMLElement
          
          const qtyText = qtyCell.innerText || qtyCell.textContent
          const isExtra = qtyText?.trim() === '—'
          
          let amount = 0
          if (!isExtra) {
            const qty = parseNumber(qtyText)
            const rate = parseNumber(rateCell.innerText || rateCell.textContent)
            amount = qty * rate
            
            const expectedText = formatINR(amount)
            if (amountCell !== target && (amountCell.innerText || amountCell.textContent) !== expectedText) {
              amountCell.innerText = expectedText
            }
          } else {
             amount = parseNumber(amountCell.innerText || amountCell.textContent)
          }

          const gstRate = parseNumber(gstCell.innerText || gstCell.textContent)
          const gstAmount = amount * (gstRate / 100)
          
          subtotal += amount
          totalGst += gstAmount
        }
      })

      const totalRows = doc.querySelectorAll('.totals-table tr')
      if (totalRows.length >= 3) {
        const subtotalCell = totalRows[0].querySelector('.text-right') as HTMLElement
        const gstCell = totalRows[1].querySelector('.text-right') as HTMLElement
        const grandCell = totalRows[2].querySelector('.text-right') as HTMLElement
        
        const expectedSubtotal = formatINR(subtotal)
        const expectedGst = formatINR(totalGst)
        const expectedGrand = formatINR(subtotal + totalGst)
        
        if (subtotalCell && subtotalCell !== target && subtotalCell.innerText !== expectedSubtotal) subtotalCell.innerText = expectedSubtotal
        if (gstCell && gstCell !== target && gstCell.innerText !== expectedGst) gstCell.innerText = expectedGst
        if (grandCell && grandCell !== target && grandCell.innerText !== expectedGrand) grandCell.innerText = expectedGrand
      }
    }

    function applyEditable() {
      const doc = iframeRef.current?.contentDocument
      if (!doc) return
      
      const editableSelectors = [
        '.items-table tbody td',
        '.meta-table td.dd',
        '.totals-table td:not(:first-child)', // Allow editing amounts, not labels 'Subtotal' etc. Actually, let's just make all totals td editable for flexibility
        '.totals-table td',
        '.client-name',
        '.company-address',
        '.invoice-title',
        '.badge',
        '.signature-title'
      ]

      if (editable) {
        doc.querySelectorAll(editableSelectors.join(', ')).forEach((el) => {
          const e = el as HTMLElement
          e.contentEditable = 'true'
        })
        doc.addEventListener('input', handleInvoiceInput)
      } else {
        doc.querySelectorAll('[contenteditable]').forEach((el) => {
          const e = el as HTMLElement
          e.removeAttribute('contenteditable')
        })
        doc.removeEventListener('input', handleInvoiceInput)
      }
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
        
        const rootClone = doc.documentElement.cloneNode(true) as HTMLElement
        rootClone.querySelectorAll('[contenteditable]').forEach(el => {
          el.removeAttribute('contenteditable')
        })
        
        return `<!DOCTYPE html>\n${rootClone.outerHTML}`
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
