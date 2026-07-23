import datetime
from decimal import Decimal
from django.test import TestCase
from billing.models import LegalEntity, FinancialYear, Invoice, InvoiceStatus
from billing.reports import FinanceReportService


class FinanceReportTests(TestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Awkward Fleet Operations Pvt Ltd",
            gstin="27AAACA9876A1Z4",
        )
        self.fy = FinancialYear.objects.create(
            name="FY 2025-26",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        self.invoice = Invoice.objects.create(
            legal_entity=self.entity,
            financial_year=self.fy,
            invoice_number="INV/2025-26/00005",
            issue_date=datetime.date(2026, 7, 23),
            status=InvoiceStatus.ISSUED,
            billing_name_snapshot="Tally Client Pvt Ltd",
            taxable_amount=Decimal("10000.00"),
            cgst_amount=Decimal("250.00"),
            sgst_amount=Decimal("250.00"),
            total_amount=Decimal("10500.00"),
            balance_amount=Decimal("10500.00"),
        )

    def test_export_tally_xml(self):
        xml = FinanceReportService.export_tally_xml(self.invoice)
        self.assertIn("INV/2025-26/00005", xml)
        self.assertIn("Tally Client Pvt Ltd", xml)
        self.assertIn("10500.00", xml)
        self.assertIn("Passenger Transport Revenue", xml)
