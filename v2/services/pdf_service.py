from sqlalchemy.orm import Session
from v2.models.invoice import Invoice

def generate_invoice_pdf(session: Session, invoice_id: str) -> bytes:
    # 1. Fetch Invoice Snapshot exclusively
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
    if not invoice:
        raise ValueError("Invoice not found")

    # Fetch nested data
    items = invoice.items
    taxes = invoice.taxes
    tds = invoice.tds

    # 2. Build HTML strictly from persisted DB snapshot
    # This prevents the invoice from changing if the master Project/Client records change later
    
    html_template = f"""
    <html>
        <head>
            <style>
                body {{ font-family: sans-serif; padding: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .totals {{ width: 50%; float: right; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>INVOICE</h1>
            <p><strong>Invoice Number:</strong> {invoice.invoice_number}</p>
            <p><strong>Date:</strong> {invoice.created_at.strftime('%Y-%m-%d')}</p>
            
            <hr>
            <h3>Billed To:</h3>
            <p><strong>{invoice.client_name or 'N/A'}</strong></p>
            <p>{invoice.client_address or 'N/A'}</p>
            <p>GSTIN: {invoice.client_gstin or 'N/A'}</p>

            <h3>Project:</h3>
            <p>{invoice.project_name or 'N/A'}</p>

            <table>
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>HSN/SAC</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
    """

    for item in items:
        html_template += f"""
                    <tr>
                        <td>{item.description}</td>
                        <td>{item.hsn_sac or ''}</td>
                        <td>{item.amount:.2f}</td>
                    </tr>
        """

    html_template += f"""
                </tbody>
            </table>

            <table class="totals">
                <tr>
                    <th>Subtotal</th>
                    <td>{invoice.subtotal:.2f}</td>
                </tr>
    """

    for tax in taxes:
        html_template += f"""
                <tr>
                    <th>{tax.tax_type} ({tax.percentage}%)</th>
                    <td>{tax.amount:.2f}</td>
                </tr>
        """

    if tds:
        html_template += f"""
                <tr>
                    <th>TDS Deducted ({tds.tds_percentage}%)</th>
                    <td>-{tds.tds_amount:.2f}</td>
                </tr>
        """

    html_template += f"""
                <tr>
                    <th><strong>Total Payable</strong></th>
                    <td><strong>{invoice.total_payable:.2f}</strong></td>
                </tr>
            </table>
        </body>
    </html>
    """

    # 3. Use the existing V1 PDF Builder
    import pdf_builder
    pdf_bytes = pdf_builder.html_to_pdf(html_template)
    
    return pdf_bytes
