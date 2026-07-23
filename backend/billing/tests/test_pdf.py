import datetime
from decimal import Decimal
from django.test import TestCase
from billing.models import LegalEntity, FinancialYear, FiscalPeriod, Invoice, InvoiceStatus, InvoiceLine
from billing.pdf_service import PDFService


class PDFServiceTests(TestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Awkward Fleet Operations Pvt Ltd",
            trade_name="Index Fleet",
            gstin="27AAACA9876A1Z4",
            registered_address="Mumbai HQ",
        )
        self.fy = FinancialYear.objects.create(
            name="FY 2025-26",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        self.invoice = Invoice.objects.create(
            legal_entity=self.entity,
            financial_year=self.fy,
            invoice_number="INV/2025-26/00001",
            status=InvoiceStatus.ISSUED,
            billing_name_snapshot="ACME Corp",
            gstin_snapshot="27AAACA1234A1Z5",
            taxable_amount=Decimal("2400.00"),
            cgst_amount=Decimal("60.00"),
            sgst_amount=Decimal("60.00"),
            total_amount=Decimal("2520.00"),
        )
        InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Sedan Local 8h/80km",
            sac_hsn_code="996601",
            unit_rate=Decimal("2400.00"),
            taxable_value=Decimal("2400.00"),
            cgst_rate=Decimal("2.5"),
            cgst_amount=Decimal("60.00"),
            sgst_rate=Decimal("2.5"),
            sgst_amount=Decimal("60.00"),
            line_total=Decimal("2520.00"),
        )

    def test_render_invoice_html(self):
        html = PDFService.render_invoice_html(self.invoice)
        self.assertIn("TAX INVOICE", html)
        self.assertIn("INV/2025-26/00001", html)
        self.assertIn("ACME Corp", html)
        self.assertIn("2520.00", html)
