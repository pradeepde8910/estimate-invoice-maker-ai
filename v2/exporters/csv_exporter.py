import csv
import io
from v2.schemas.report import ReportResult

def export_csv(result: ReportResult) -> bytes:
    """
    Exports a ReportResult to CSV format and returns the bytes.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=result.columns)
    
    # Write header
    writer.writeheader()
    
    # Write rows
    for row in result.rows:
        writer.writerow(row)
        
    # Write empty row for separation
    writer.writerow({col: "" for col in result.columns})
    
    # Write totals
    for key, value in result.totals.items():
        totals_row = {col: "" for col in result.columns}
        totals_row[result.columns[0]] = key
        totals_row[result.columns[1]] = value
        writer.writerow(totals_row)
        
    return output.getvalue().encode('utf-8')
