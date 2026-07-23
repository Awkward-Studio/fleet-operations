from .models import Invoice, InvoiceStatus


class PDFService:
    @staticmethod
    def render_invoice_html(invoice: Invoice) -> str:
        is_draft = invoice.status == InvoiceStatus.DRAFT
        watermark = '<div style="position: absolute; top: 300px; left: 50px; font-size: 60px; color: rgba(239, 68, 68, 0.15); transform: rotate(-30deg); font-weight: bold; pointer-events: none;">DRAFT PREVIEW - NOT AN INVOICE</div>' if is_draft else ''

        lines_html = ""
        for line in invoice.lines.all():
            lines_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{line.description}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{line.sac_hsn_code}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">₹{line.taxable_value:.2f}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">{line.cgst_rate}% (₹{line.cgst_amount:.2f})</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">{line.sgst_rate}% (₹{line.sgst_amount:.2f})</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold;">₹{line.line_total:.2f}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice {invoice.invoice_number or invoice.id}</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1e293b; padding: 40px; margin: 0; background: #fff; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #3b49df; padding-bottom: 20px; }}
        .brand {{ font-size: 24px; font-weight: bold; color: #3b49df; }}
        .meta {{ font-size: 13px; color: #64748b; line-height: 1.5; }}
        .bill-grid {{ display: flex; justify-content: space-between; margin-top: 30px; gap: 40px; }}
        .box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; flex: 1; font-size: 13px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 30px; font-size: 13px; }}
        th {{ background: #f1f5f9; text-align: left; padding: 10px; border-bottom: 2px solid #cbd5e1; font-size: 11px; text-transform: uppercase; color: #475569; }}
        .totals {{ margin-top: 20px; width: 300px; margin-left: auto; font-size: 13px; }}
        .totals-row {{ display: flex; justify-content: space-between; padding: 6px 0; }}
        .totals-row.grand {{ font-size: 16px; font-weight: bold; border-top: 2px solid #1e293b; color: #3b49df; padding-top: 10px; }}
    </style>
</head>
<body>
    {watermark}
    <div class="header">
        <div>
            <div class="brand">{invoice.legal_entity.legal_name}</div>
            <div class="meta">
                {invoice.legal_entity.trade_name or ''}<br>
                GSTIN: {invoice.legal_entity.gstin or 'N/A'} | PAN: {invoice.legal_entity.pan or 'N/A'}<br>
                {invoice.legal_entity.registered_address or ''}
            </div>
        </div>
        <div style="text-align: right;">
            <h2 style="margin: 0; color: #1e293b;">{"TAX INVOICE" if not is_draft else "DRAFT PROFORMA"}</h2>
            <div style="font-size: 16px; font-weight: bold; color: #3b49df; margin-top: 4px;">{invoice.invoice_number or 'DRAFT'}</div>
            <div class="meta" style="margin-top: 8px;">
                Date: {invoice.issue_date}<br>
                Due Date: {invoice.due_date}<br>
                Place of Supply: {invoice.place_of_supply}
            </div>
        </div>
    </div>

    <div class="bill-grid">
        <div class="box">
            <strong>Billed To:</strong><br>
            <span style="font-size: 15px; font-weight: bold; color: #0f172a;">{invoice.billing_name_snapshot}</span><br>
            GSTIN: {invoice.gstin_snapshot or 'Unregistered'}<br>
            {invoice.billing_address_snapshot or ''}
        </div>
        <div class="box">
            <strong>Remittance & Payment Terms:</strong><br>
            Bank: {invoice.legal_entity.bank_name or 'HDFC Bank'}<br>
            Account: {invoice.legal_entity.bank_account_number or '50200012345678'}<br>
            IFSC: {invoice.legal_entity.ifsc_code or 'HDFC0001234'}<br>
            PO Number: {invoice.po_number or 'N/A'}
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Description</th>
                <th style="text-align: center;">SAC</th>
                <th style="text-align: right;">Taxable (₹)</th>
                <th style="text-align: right;">CGST</th>
                <th style="text-align: right;">SGST</th>
                <th style="text-align: right;">Amount (₹)</th>
            </tr>
        </thead>
        <tbody>
            {lines_html}
        </tbody>
    </table>

    <div class="totals">
        <div class="totals-row">
            <span>Taxable Amount:</span>
            <span>₹{invoice.taxable_amount:.2f}</span>
        </div>
        <div class="totals-row">
            <span>CGST (2.5%):</span>
            <span>₹{invoice.cgst_amount:.2f}</span>
        </div>
        <div class="totals-row">
            <span>SGST (2.5%):</span>
            <span>₹{invoice.sgst_amount:.2f}</span>
        </div>
        <div class="totals-row grand">
            <span>Total Amount:</span>
            <span>₹{invoice.total_amount:.2f}</span>
        </div>
    </div>
</body>
</html>"""
        return html
