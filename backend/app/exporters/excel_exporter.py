import io
from openpyxl import Workbook
from app.schemas.report import ReportResult

def export_excel(result: ReportResult) -> bytes:
    """
    Exports a ReportResult to Excel (.xlsx) format and returns the bytes.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = result.report_type
    
    # Write header
    ws.append(result.columns)
    
    # Write rows
    for row_dict in result.rows:
        row_list = [row_dict.get(col, "") for col in result.columns]
        ws.append(row_list)
        
    # Write empty row
    ws.append([])
    
    # Write totals
    for key, value in result.totals.items():
        totals_row = [""] * len(result.columns)
        if len(result.columns) >= 2:
            totals_row[0] = key
            totals_row[1] = value
        else:
            totals_row[0] = f"{key}: {value}"
        ws.append(totals_row)
        
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
