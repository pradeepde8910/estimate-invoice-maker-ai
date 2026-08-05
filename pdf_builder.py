"""
Markdown → PDF renderer for client-facing documents (quotation, BRD, SRS,
invoice, cover letter). Converts the same Markdown shown on-screen into a
print-ready PDF with a consistent corporate look — used so "what you see
(and edit) is what gets exported."
"""

from __future__ import annotations

import io
import re

import markdown as md
from PIL import Image
from xhtml2pdf import pisa

from organization import BRANDING_DIR

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


_PAGE_FOOTER_CSS = """
@page {
    size: A4;
    margin-bottom: 1.6cm;
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        bottom: 0.6cm;
        margin-left: 1.6cm;
        margin-right: 1.6cm;
        height: 1cm;
    }
}
"""
_FOOTER_DIV = (
    '<div id="footer_content" style="text-align:center;font-size:7.5pt;color:#94a3b8;">'
    "Page <pdf:pagenumber /> of <pdf:pagecount /></div>"
)


_WEB_FONT_LINK_PATTERN = re.compile(
    r'<link[^>]+href="https://fonts\.g(?:oogleapis|static)\.com[^"]*"[^>]*>\s*'
)


def html_to_pdf(html_document: str) -> bytes:
    """Render an already-complete, self-styled HTML document (e.g. the
    invoice template) to PDF — no Markdown conversion step, just the same
    font/emoji/image fixes applied to any xhtml2pdf render."""
    # Google Fonts <link> tags are for the on-screen iframe (a real browser).
    # xhtml2pdf can't bind custom @font-face text runs reliably regardless
    # (confirmed separately), so fetching them here only adds several
    # seconds of network latency — and would break entirely offline — for
    # zero visual benefit. Stripped before rendering; PDF keeps its safe
    # system-font fallback.
    html_document = _WEB_FONT_LINK_PATTERN.sub("", html_document)
    html_document = html_document.replace("₹", "Rs. ")
    html_document = _EMOJI_PATTERN.sub("", html_document)
    html_document = _size_branding_images(html_document)

    if "</head>" in html_document:
        html_document = html_document.replace("</head>", f"<style>{_PAGE_FOOTER_CSS}</style></head>", 1)
    if "</body>" in html_document:
        html_document = html_document.replace("</body>", f"{_FOOTER_DIV}</body>", 1)

    buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html_document), dest=buffer, link_callback=_resolve_uri)
    if result.err:
        raise RuntimeError("Failed to render PDF")
    return buffer.getvalue()
