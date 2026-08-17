import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from v2.schemas.report import ReportResult

def export_pdf(result: ReportResult) -> bytes:
    """
    Exports a ReportResult to PDF format and returns the bytes.
    """
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    title = Paragraph(f"Report: {result.report_type}", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Prepare table data
    data = [result.columns] # Header
    
    for row_dict in result.rows:
        row_list = [str(row_dict.get(col, "")) for col in result.columns]
        data.append(row_list)
        
    # Totals
    for key, value in result.totals.items():
        totals_row = [""] * len(result.columns)
        if len(result.columns) >= 2:
            totals_row[0] = str(key)
            totals_row[1] = str(value)
        else:
            totals_row[0] = f"{key}: {value}"
        data.append(totals_row)
        
    # Table Style
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    return output.getvalue()
