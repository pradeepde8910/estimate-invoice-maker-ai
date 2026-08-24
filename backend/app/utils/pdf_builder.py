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

from app.utils.organization import BRANDING_DIR

# WeasyPrint honors standard CSS max-width/max-height, so we don't need manual
# PIL-based image resizing hacks like we did for xhtml2pdf.

# Emoji strip pattern for fonts that don't support emojis.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)

CSS = """
@page {
    size: A4;
    margin: 2.2cm 1.6cm 2.4cm 1.6cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 7.5pt;
        color: #94a3b8;
    }
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    color: #1e293b;
    line-height: 1.5;
    font-variant-numeric: tabular-nums;
    text-rendering: optimizeLegibility;
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
    page-break-inside: auto;
}
tr {
    page-break-inside: avoid;
    page-break-after: auto;
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
img {
    max-width: 200px;
    max-height: 56px;
    object-fit: contain;
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
    from weasyprint import HTML

    markdown_text = _EMOJI_PATTERN.sub("", markdown_text)
    markdown_text = _MERMAID_BLOCK_PATTERN.sub(_MERMAID_PLACEHOLDER, markdown_text)
    markdown_text = _ensure_blank_line_before_lists(markdown_text)
    
    body_html = md.markdown(markdown_text, extensions=["tables", "fenced_code", "nl2br"])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>{CSS}</style>
    </head>
    <body>
        {body_html}
    </body>
    </html>
    """
    return HTML(string=html, base_url=str(BRANDING_DIR)).write_pdf()


_WEB_FONT_LINK_PATTERN = re.compile(
    r'<link[^>]+href="https://fonts\.g(?:oogleapis|static)\.com[^"]*"[^>]*>\s*'
)


def html_to_pdf(html_document: str) -> bytes:
    """Render a self-contained HTML invoice to PDF.

    Uses Playwright (headless Chromium) when available for pixel-perfect
    output identical to the on-screen preview. Falls back to WeasyPrint
    if Playwright isn't installed, errors, or doesn't finish within the
    timeout (Playwright's sync API drives its own subprocess-based driver;
    running it in a dedicated worker thread with a bounded wait means a
    hang there — e.g. an event-loop/subprocess incompatibility on the
    calling thread — can never stall the request indefinitely).
    """
    import concurrent.futures
    import platform

    def _worker():
        if platform.system() == "Windows":
            # Playwright's sync API creates its driver subprocess via
            # asyncio.new_event_loop() on whatever thread it's called from.
            # The default policy on a plain worker thread yields a
            # SelectorEventLoop, which raises NotImplementedError on
            # subprocess creation on Windows — only ProactorEventLoop
            # supports subprocesses there. Only WindowsProactorEventLoopPolicy
            # loops support subprocesses, so it must be installed before
            # sync_playwright() constructs its loop.
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return _html_to_pdf_playwright(html_document)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_worker).result(timeout=25)
    except Exception as e:
        with open("playwright_error.log", "w") as f:
            f.write(f"PLAYWRIGHT ERROR: {e!r}\n")
        return _html_to_pdf_weasyprint(html_document)


def _inline_branding_images(html_document: str) -> str:
    """Replace /branding/<file> src attributes with base64 data URIs read
    straight off disk. Playwright renders a raw HTML string with no server
    behind it, so a server-relative URL like "/branding/logo.png" can only
    resolve by guessing the uvicorn host:port — fragile, and wrong whenever
    the app isn't bound to that exact port. Inlining removes the network
    hop (and the guesswork) entirely.
    """
    import base64
    import mimetypes

    def _replace(match: "re.Match[str]") -> str:
        filename = match.group(1)
        path = BRANDING_DIR / filename
        if not path.is_file():
            return match.group(0)
        mime = mimetypes.guess_type(filename)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{data}"'

    return re.sub(r'src="/branding/([^"]+)"', _replace, html_document)


def _html_to_pdf_playwright(html_document: str) -> bytes:
    """Pixel-perfect PDF via headless Chromium."""
    from playwright.sync_api import sync_playwright

    # We force a white background and remove padding so the PDF doesn't look like a UI screen.
    html_document = _inline_branding_images(html_document)
    style_override = "<style>@media screen { body { background-color: #ffffff !important; padding: 0 !important; } .invoice-card { box-shadow: none !important; border-radius: 0 !important; padding: 0 !important; max-width: none !important; } }</style>"
    if "</head>" in html_document:
        html_document = html_document.replace("</head>", style_override + "</head>")
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
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


def _html_to_pdf_weasyprint(html_document: str) -> bytes:
    """Fallback using WeasyPrint (good CSS support without full Chromium engine)."""
    from weasyprint import HTML
    
    # WeasyPrint understands standard print media CSS
    style_override = """
    <style>
        @page {
            size: A4;
            margin: 1.5cm;
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 7.5pt;
                color: #94a3b8;
                font-family: sans-serif;
            }
        }
        @media print {
            body { padding: 0 !important; background-color: #ffffff !important; }
            .invoice-card { box-shadow: none !important; border-radius: 0 !important; padding: 0 !important; max-width: none !important; }
        }
    </style>
    """
    
    if "</head>" in html_document:
        html_document = html_document.replace("</head>", style_override + "</head>")

    html_document = _EMOJI_PATTERN.sub("", html_document)

    # We provide base_url=BRANDING_DIR so that WeasyPrint can resolve /branding/ files natively
    # We replace /branding/ with just the local filename so WeasyPrint can find it in the directory.
    html_document = html_document.replace('src="/branding/', 'src="')
    
    return HTML(string=html_document, base_url=str(BRANDING_DIR)).write_pdf()


