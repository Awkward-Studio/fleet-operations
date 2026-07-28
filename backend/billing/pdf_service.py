import hashlib

from django.core.files.base import ContentFile

from media_store.models import UploadedAsset
from media_store.storage import upload_asset

from .models import Invoice, InvoiceDocument, InvoiceStatus


class PDFService:
    GENERATION_VERSION = "invoice-pdf-v1"

    @staticmethod
    def render_invoice_pdf(invoice: Invoice) -> bytes:
        """Create a deterministic, dependency-free PDF for durable storage."""
        heading = (
            "DRAFT PREVIEW - NOT AN INVOICE"
            if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.REVIEW}
            else "TAX INVOICE"
        )
        rows = [
            heading,
            f"Invoice: {invoice.invoice_number or f'DRAFT-{invoice.id}'}",
            f"Supplier: {invoice.legal_entity.legal_name}",
            f"Bill to: {invoice.billing_name_snapshot}",
            f"Issue date: {invoice.issue_date}  Due date: {invoice.due_date}",
            f"Taxable: INR {invoice.taxable_amount:.2f}",
            f"CGST: INR {invoice.cgst_amount:.2f}  SGST: INR {invoice.sgst_amount:.2f}  IGST: INR {invoice.igst_amount:.2f}",
            f"Total: INR {invoice.total_amount:.2f}",
        ]
        rows.extend(
            f"{line.description}: INR {line.line_total:.2f}"
            for line in invoice.lines.all()
        )
        escaped = [
            row.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            for row in rows
        ]
        commands = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for index, row in enumerate(escaped):
            commands.append(f"({row}) Tj")
            if index != len(escaped) - 1:
                commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        output = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(output))
            output.extend(f"{index} 0 obj\n".encode())
            output.extend(obj)
            output.extend(b"\nendobj\n")
        xref = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode())
        output.extend(
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
        )
        return bytes(output)

    @staticmethod
    def get_or_create_document(invoice: Invoice, request=None) -> InvoiceDocument:
        if invoice.status in {
            InvoiceStatus.ISSUED,
            InvoiceStatus.SENT,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID,
        }:
            frozen = invoice.documents.filter(is_frozen=True).first()
            if frozen:
                return frozen
        pdf_bytes = PDFService.render_invoice_pdf(invoice)
        checksum = hashlib.sha256(pdf_bytes).hexdigest()
        version = (invoice.documents.first().version + 1) if invoice.documents.exists() else 1
        upload = ContentFile(pdf_bytes, name=f"invoice-{invoice.id}-v{version}.pdf")
        upload.content_type = "application/pdf"
        asset = upload_asset(
            upload,
            kind=UploadedAsset.KIND_INVOICE,
            folder="invoices",
            request=request,
            metadata={
                "invoice_id": invoice.id,
                "version": version,
                "generation_version": PDFService.GENERATION_VERSION,
            },
        )
        return InvoiceDocument.objects.create(
            invoice=invoice,
            version=version,
            generation_version=PDFService.GENERATION_VERSION,
            status_snapshot=invoice.status,
            checksum_sha256=checksum,
            attachment=asset,
            is_frozen=invoice.status not in {InvoiceStatus.DRAFT, InvoiceStatus.REVIEW},
            generated_by=request.user if request and request.user.is_authenticated else None,
        )
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
