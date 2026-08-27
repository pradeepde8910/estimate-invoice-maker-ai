import io
from xml.sax.saxutils import escape as _xml_escape
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.schemas.report import ReportResult

# Landscape rather than the reportlab default (portrait US Letter): with up
# to a dozen columns (see InvoiceReport), portrait width isn't enough and
# reportlab's Table silently sizes every column to its natural content
# width regardless of the page frame — the result renders with columns
# running off both page edges rather than erroring, so it's easy to ship
# a report export that's actually unreadable without ever seeing an error.
# Wrapping every cell in a Paragraph (rather than a bare string) is the
# other half of that fix: Paragraph text wraps to the column's real width,
# so a long value grows the row's height instead of overflowing sideways.
_PAGE_SIZE = landscape(A4)
_MARGIN = 14 * mm
_AVAILABLE_WIDTH = _PAGE_SIZE[0] - 2 * _MARGIN

_styles = getSampleStyleSheet()
_header_style = ParagraphStyle('ReportHeader', parent=_styles['Normal'], fontSize=8, leading=10, textColor=colors.whitesmoke, fontName='Helvetica-Bold')
_cell_style = ParagraphStyle('ReportCell', parent=_styles['Normal'], fontSize=7.5, leading=9.5)
_totals_style = ParagraphStyle('ReportTotals', parent=_styles['Normal'], fontSize=8, leading=10, fontName='Helvetica-Bold')


def _fmt(value) -> str:
    """
    Formats a cell value AND escapes it for use as Paragraph text.
    reportlab's Paragraph parses its input as a small XML/HTML-like markup
    subset (for <b>, <i>, line breaks, etc.) rather than treating it as
    plain text — so an unescaped '&' or '<' in real data (e.g. a client
    named "R&D Solutions <Pvt> Ltd.") gets silently swallowed or mangled
    into something else entirely instead of raising an error. Every string
    that reaches a Paragraph in this module must go through this (or
    _xml_escape directly for values that don't need numeric formatting).
    """
    if value is None:
        return ""
    if isinstance(value, float):
        # Report values are already plain floats/ints by the time they reach
        # here (each report generator converts Decimal -> float) — format
        # with thousands separators so a wide PDF table reads like a
        # financial document, not a raw data dump.
        return f"{value:,.2f}"
    return _xml_escape(str(value))


def export_pdf(result: ReportResult) -> bytes:
    """
    Exports a ReportResult to a landscape A4 PDF with word-wrapped, evenly
    sized columns so the table always fits the page regardless of how many
    columns the report (or the caller's column selection) ends up with.
    """
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=_PAGE_SIZE,
        leftMargin=_MARGIN, rightMargin=_MARGIN, topMargin=_MARGIN, bottomMargin=_MARGIN,
    )
    elements = []

    title = Paragraph(f"Report: {_xml_escape(result.report_type)}", _styles['Title'])
    elements.append(title)
    generated = Paragraph(f"Generated: {result.generated_at.strftime('%d %b %Y, %I:%M %p')}", _styles['Normal'])
    elements.append(generated)
    elements.append(Spacer(1, 10))

    columns = result.columns or []
    if not columns:
        elements.append(Paragraph("No columns selected.", _styles['Normal']))
        doc.build(elements)
        return output.getvalue()

    col_width = _AVAILABLE_WIDTH / len(columns)

    data = [[Paragraph(_xml_escape(str(col)), _header_style) for col in columns]]

    if not result.rows:
        # An empty result set is a legitimate outcome (e.g. a client with no
        # payments yet), not an error — render one clearly-labeled row
        # instead of a table with only a header, which could read as a
        # broken/truncated export.
        empty_row = [Paragraph("No matching records" if i == 0 else "", _cell_style) for i in range(len(columns))]
        data.append(empty_row)
    else:
        for row_dict in result.rows:
            data.append([Paragraph(_fmt(row_dict.get(col, "")), _cell_style) for col in columns])

    body_row_count = len(data) - 1  # excludes header, used to style the totals rows below

    for key, value in result.totals.items():
        key_str = _xml_escape(str(key))
        totals_row = [Paragraph("", _totals_style) for _ in columns]
        totals_row[0] = Paragraph(key_str, _totals_style)
        if len(columns) >= 2:
            totals_row[1] = Paragraph(_fmt(value), _totals_style)
        else:
            totals_row[0] = Paragraph(f"{key_str}: {_fmt(value)}", _totals_style)
        data.append(totals_row)

    table = Table(data, colWidths=[col_width] * len(columns), repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, body_row_count), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    if len(data) > body_row_count + 1:
        # Totals rows start right after the body rows (and the header) —
        # give them a distinct background so they read as a summary rather
        # than one more data row.
        style.append(('BACKGROUND', (0, body_row_count + 1), (-1, -1), colors.HexColor('#e2e8f0')))
        style.append(('LINEABOVE', (0, body_row_count + 1), (-1, body_row_count + 1), 1, colors.HexColor('#1e293b')))
    table.setStyle(TableStyle(style))

    elements.append(table)
    doc.build(elements)

    return output.getvalue()
