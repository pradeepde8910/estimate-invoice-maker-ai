"""Strips script-execution vectors from server-stored, full-document HTML
(the generated invoice template - a complete <html><head><style>...
document, not a fragment).

This is deliberately narrow rather than a full allowlist sanitizer (like
bleach): the invoice template needs to keep its <style> block, inline
`style` attributes, and full document structure intact, and a
fragment-oriented sanitizer would mangle that. The real stop for script
execution is the sandboxed iframe (HtmlFrame.tsx renders with
sandbox="allow-same-origin" and no allow-scripts, so no script runs
client-side regardless). This is defense-in-depth for anything that reads
invoice_html outside that iframe.
"""
import re

_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_SCRIPT_TAG_UNCLOSED_RE = re.compile(r"<script\b[^>]*/?>", re.IGNORECASE)
_EVENT_HANDLER_ATTR_RE = re.compile(
    r'''\s+on[a-z]+\s*=\s*(".*?"|'.*?'|[^\s>]+)''', re.IGNORECASE | re.DOTALL
)
_JAVASCRIPT_URI_RE = re.compile(
    r'''(href|src|action|formaction)\s*=\s*(["'])\s*javascript:[^"']*\2''',
    re.IGNORECASE,
)
_DANGEROUS_TAGS_RE = re.compile(
    r"<(iframe|object|embed|link\s+rel=[\"']?import[\"']?)\b[^>]*>(.*?</\1\s*>)?",
    re.IGNORECASE | re.DOTALL,
)


def strip_script_vectors(html: str) -> str:
    if not html:
        return html
    html = _SCRIPT_TAG_RE.sub("", html)
    html = _SCRIPT_TAG_UNCLOSED_RE.sub("", html)
    html = _EVENT_HANDLER_ATTR_RE.sub("", html)
    html = _JAVASCRIPT_URI_RE.sub(lambda m: f'{m.group(1)}="#"', html)
    html = _DANGEROUS_TAGS_RE.sub("", html)
    return html
