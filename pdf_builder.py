"""
Markdown → PDF renderer for client-facing documents (quotation, BRD, SRS,
invoice, cover letter). Converts the same Markdown shown on-screen into a
print-ready PDF with a consistent corporate look — used so "what you see
(and edit) is what gets exported."
"""

from __future__ import annotations

import io
import os
import re

import markdown as md
from PIL import Image
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa

from organization import BRANDING_DIR

# ── Register Segoe UI (ships with every Windows 10+ install) so xhtml2pdf
# renders the same modern sans-serif used on-screen instead of falling back
# to bare Helvetica.  Segoe UI also contains the ₹ glyph, letting us keep
# the rupee sign in PDFs rather than swapping it for "Rs.".
_FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
_HAS_SEGOE = False
try:
    pdfmetrics.registerFont(TTFont('SegoeUI', os.path.join(_FONT_DIR, 'segoeui.ttf')))
    pdfmetrics.registerFont(TTFont('SegoeUI-Bold', os.path.join(_FONT_DIR, 'segoeuib.ttf')))
    pdfmetrics.registerFont(TTFont('SegoeUI-Italic', os.path.join(_FONT_DIR, 'segoeuii.ttf')))
    pdfmetrics.registerFont(TTFont('SegoeUI-BoldItalic', os.path.join(_FONT_DIR, 'segoeuiz.ttf')))
    addMapping('SegoeUI', 0, 0, 'SegoeUI')
    addMapping('SegoeUI', 1, 0, 'SegoeUI-Bold')
    addMapping('SegoeUI', 0, 1, 'SegoeUI-Italic')
    addMapping('SegoeUI', 1, 1, 'SegoeUI-BoldItalic')
    _HAS_SEGOE = True
except Exception:
    pass

_PDF_FONT = 'SegoeUI' if _HAS_SEGOE else 'Helvetica'

# xhtml2pdf renders <img> at its natural pixel size unless width/height are
# set explicitly — max-width/max-height in CSS are not honored. Branding
# assets (logo, signature, seal) are uploaded at arbitrary resolutions, so we
# measure them with Pillow and inject explicit point dimensions, capped to
# fit a small letterhead-sized box while preserving aspect ratio.
_MAX_IMG_HEIGHT_PT = 56
_MAX_IMG_WIDTH_PT = 200


def _size_branding_images(html: str) -> str:
    def resize(match: re.Match) -> str:
        tag = match.group(0)
        src_match = re.search(r'src="([^"]+)"', tag)
        if not src_match or not src_match.group(1).startswith("/branding/"):
            return tag
        path = BRANDING_DIR / src_match.group(1).removeprefix("/branding/")
        if not path.exists():
            return tag
        try:
            with Image.open(path) as im:
                w, h = im.size
        except Exception:
            return tag
        scale = min(_MAX_IMG_HEIGHT_PT / h, _MAX_IMG_WIDTH_PT / w, 1)
        new_w, new_h = round(w * scale), round(h * scale)
        closing = "/>" if tag.rstrip().endswith("/>") else ">"
        return tag[: -len(closing)] + f' width="{new_w}" height="{new_h}"{closing}'

    return re.sub(r"<img[^>]*>", resize, html)

# xhtml2pdf's base PDF fonts have no emoji glyphs (they render as black boxes),
# so PDF exports strip them; on-screen Markdown views keep them.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


def _resolve_uri(uri: str, _rel: str) -> str:
    """Resolve /branding/<file> references to the local file on disk so
    xhtml2pdf can embed images without making an HTTP round-trip."""
    if uri.startswith("/branding/"):
        candidate = BRANDING_DIR / uri.removeprefix("/branding/")
        if candidate.exists():
            return str(candidate)
    return uri

CSS = """
@page {
    size: A4;
    margin: 2.2cm 1.6cm 2.4cm 1.6cm;
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        bottom: 1cm;
        margin-left: 1.6cm;
        margin-right: 1.6cm;
        height: 1cm;
    }
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #1e293b;
    line-height: 1.5;
}
h1 {
    font-size: 18pt;
    color: #0b5129;
    margin: 6pt 0 2pt 0;
}
h2 {
    font-size: 13pt;
    color: #0f172a;
    margin: 16pt 0 6pt 0;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 3pt;
}
h3 {
    font-size: 11pt;
    color: #0f172a;
    margin: 12pt 0 4pt 0;
}
p { margin: 4pt 0; }
hr {
    border: none;
    border-top: 1px solid #cbd5e1;
    margin: 10pt 0;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 8pt 0;
}
th, td {
    border: 1px solid #e2e8f0;
    padding: 5pt 7pt;
    font-size: 9pt;
    text-align: left;
}
th {
    background-color: #f0fdf6;
    color: #0b5129;
    font-weight: bold;
}
strong { color: #0f172a; }
ul, ol { margin: 4pt 0 4pt 18pt; }
pre {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4pt;
    padding: 8pt 10pt;
    margin: 8pt 0;
    font-family: Courier, monospace;
    font-size: 8pt;
    color: #334155;
    white-space: pre-wrap;
    word-wrap: break-word;
}
code {
    font-family: Courier, monospace;
    font-size: 8pt;
    background-color: #f1f5f9;
    padding: 1pt 3pt;
    border-radius: 2pt;
}
pre code {
    background-color: transparent;
    padding: 0;
}
blockquote {
    border-left: 3pt solid #16a34f;
    background-color: #f0fdf6;
    color: #334155;
    margin: 8pt 0;
    padding: 6pt 12pt;
}
"""

# xhtml2pdf can't execute JavaScript, so Mermaid diagrams (which the
# on-screen viewer renders live) would otherwise dump their raw diagram
# syntax as an unstyled wall of text. Swapped for a clearly-labeled note —
# the raw DSL isn't meaningful to a document reader anyway.
_MERMAID_BLOCK_PATTERN = re.compile(r"```mermaid\n.*?```", re.DOTALL)
_MERMAID_PLACEHOLDER = (
    "\n> **Diagram** — an interactive version of this diagram is available in the on-screen document view.\n"
)

# python-markdown (unlike the on-screen remark/GFM renderer) requires a
# blank line before a list can start — a paragraph immediately followed by
# "- item" lines otherwise renders as one run-on paragraph with literal
# leading dashes instead of a bulleted list. LLM-generated Markdown doesn't
# reliably include that blank line, so it's inserted here before conversion.
_LIST_ITEM_PATTERN = re.compile(r"^(\s*)([-*+]|\d+\.)\s+")


def _ensure_blank_line_before_lists(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if _LIST_ITEM_PATTERN.match(line):
            prev = out[-1] if out else ""
            prev_is_list_or_blank = prev.strip() == "" or _LIST_ITEM_PATTERN.match(prev) is not None
            if not prev_is_list_or_blank:
                out.append("")
        out.append(line)
    return "\n".join(out)


def markdown_to_pdf(markdown_text: str) -> bytes:
    # xhtml2pdf's base PDF fonts (WinAnsi/Latin-1) can't render the ₹ glyph —
    # custom TrueType font-face embedding didn't bind reliably either, so we
    # swap to the ASCII-safe "Rs." prefix for PDF exports specifically.
    # On-screen views keep the ₹ symbol; only the exported PDF differs.
    markdown_text = markdown_text.replace("₹", "Rs. ")
    markdown_text = _EMOJI_PATTERN.sub("", markdown_text)
    markdown_text = _MERMAID_BLOCK_PATTERN.sub(_MERMAID_PLACEHOLDER, markdown_text)
    markdown_text = _ensure_blank_line_before_lists(markdown_text)
    body_html = md.markdown(markdown_text, extensions=["tables", "fenced_code", "nl2br"])
    body_html = _size_branding_images(body_html)
    html = f"""
    <html>
    <head><style>{CSS}</style></head>
    <body>
        {body_html}
        <div id="footer_content" style="text-align:center;font-size:7.5pt;color:#94a3b8;">
            Page <pdf:pagenumber /> of <pdf:pagecount />
        </div>
    </body>
    </html>
    """
    buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html), dest=buffer, link_callback=_resolve_uri)
    if result.err:
        raise RuntimeError("Failed to render PDF")
    return buffer.getvalue()


_PAGE_FOOTER_CSS = f"""
@page {{
    size: A4;
    margin: 1.2cm 1.2cm 2cm 1.2cm;
    @frame footer_frame {{
        -pdf-frame-content: footer_content;
        bottom: 0.6cm;
        margin-left: 1.2cm;
        margin-right: 1.2cm;
        height: 1cm;
    }}
}}
body {{ padding: 0 !important; background-color: #ffffff !important; }}
.invoice-card {{ padding: 12px !important; max-width: none !important; box-shadow: none !important; border-radius: 0 !important; }}
* {{ font-family: {_PDF_FONT}, Helvetica, Arial, sans-serif !important; }}
"""
_FOOTER_DIV = (
    '<div id="footer_content" style="text-align:center;font-size:7.5pt;color:#94a3b8;">'
    "Page <pdf:pagenumber /> of <pdf:pagecount /></div>"
)


_WEB_FONT_LINK_PATTERN = re.compile(
    r'<link[^>]+href="https://fonts\.g(?:oogleapis|static)\.com[^"]*"[^>]*>\s*'
)


def html_to_pdf(html_document: str) -> bytes:
    """Render a self-contained HTML invoice to PDF.

    Uses Playwright (headless Chromium) when available for pixel-perfect
    output identical to the on-screen preview — same Google Sans fonts,
    ₹ symbol, CSS layout, shadows, and rounded corners.  Falls back to
    the legacy xhtml2pdf path if Playwright isn't installed.
    """
    try:
        return _html_to_pdf_playwright(html_document)
    except Exception as e:
        with open("playwright_error.log", "w") as f:
            f.write(f"PLAYWRIGHT ERROR: {e}\n")
        return _html_to_pdf_xhtml2pdf(html_document)


def _html_to_pdf_playwright(html_document: str) -> bytes:
    """Pixel-perfect PDF via headless Chromium."""
    from playwright.sync_api import sync_playwright

    # 1. Playwright renders raw HTML, so it cannot resolve relative URLs like "/branding/logo.png".
    #    We rewrite them to point directly to the local uvicorn server.
    # 2. We force a white background and remove padding so the PDF doesn't look like a UI screen.
    html_document = html_document.replace('src="/branding/', 'src="http://localhost:8010/branding/')
    style_override = "<style>@media screen { body { background-color: #ffffff !important; padding: 0 !important; } .invoice-card { box-shadow: none !important; border-radius: 0 !important; padding: 0 !important; max-width: none !important; } }</style>"
    if "</head>" in html_document:
        html_document = html_document.replace("</head>", style_override + "</head>")
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Use 'screen' media so the PDF looks identical to the on-screen
        # iframe — including background colours, shadows, and rounded
        # corners.  (The default 'print' media triggers @media print
        # overrides that strip padding/shadows.)
        page.emulate_media(media='screen')
        page.set_content(html_document, wait_until='networkidle')
        pdf_bytes = page.pdf(
            format='A4',
            print_background=True,
            margin={
                'top': '1.5cm',
                'bottom': '1.5cm',
                'left': '1.5cm',
                'right': '1.5cm',
            },
            display_header_footer=True,
            header_template='<span></span>',
            footer_template=(
                '<div style="text-align:center;width:100%;font-size:7.5pt;'
                'color:#94a3b8;font-family:sans-serif;">'
                'Page <span class="pageNumber"></span> of '
                '<span class="totalPages"></span></div>'
            ),
        )
        browser.close()
        return pdf_bytes


def _html_to_pdf_xhtml2pdf(html_document: str) -> bytes:
    """Legacy fallback using xhtml2pdf (limited CSS support)."""
    html_document = _WEB_FONT_LINK_PATTERN.sub("", html_document)
    html_document = html_document.replace("₹", "Rs.")
    html_document = _EMOJI_PATTERN.sub("", html_document)
    html_document = _size_branding_images(html_document)

    # Fix old signature layout for xhtml2pdf
    html_document = re.sub(
        r'<table\s+class="layout-table">\s*<tr>\s*<td\s+style="text-align:\s*right;">\s*'
        r'<table\s+style="display:\s*inline-table;">\s*<tr>\s*<td\s+class="signature-box">'
        r'(.*?)</td>\s*</tr>\s*</table>\s*</td>\s*</tr>\s*</table>',
        r'<table class="layout-table"><tr>'
        r'<td width="60%"></td>'
        r'<td width="40%"><div class="signature-box">\1</div></td>'
        r'</tr></table>',
        html_document,
        flags=re.DOTALL,
    )

    if "</head>" in html_document:
        html_document = html_document.replace("</head>", f"<style>{_PAGE_FOOTER_CSS}</style></head>", 1)
    if "</body>" in html_document:
        html_document = html_document.replace("</body>", f"{_FOOTER_DIV}</body>", 1)

    buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_document), dest=buffer, link_callback=_resolve_uri)
    if result.err:
        raise RuntimeError("Failed to render PDF")
    return buffer.getvalue()


