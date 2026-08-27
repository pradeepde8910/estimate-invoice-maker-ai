import csv
import io
from app.schemas.report import ReportResult

def export_csv(result: ReportResult) -> bytes:
    """
    Exports a ReportResult to CSV format and returns the bytes.
    """
    if not result.columns:
        return "No columns selected.\n".encode('utf-8')

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
        if len(result.columns) >= 2:
            totals_row[result.columns[0]] = key
            totals_row[result.columns[1]] = value
        elif result.columns:
            # Only one column selected — there's no second cell to hold the
            # value, so fold it into the one cell that exists rather than
            # indexing past the end of result.columns.
            totals_row[result.columns[0]] = f"{key}: {value}"
        writer.writerow(totals_row)
        
    return output.getvalue().encode('utf-8')
