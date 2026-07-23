import datetime
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from billing.models import (
    LegalEntity,
    FinancialYear,
    FiscalPeriod,
    InvoiceStatus,
    TripCloseout,
    CloseoutStatus,
    TripCharge,
    ChargeCategory,
)
from billing.services import InvoiceService
from fleet.models import Trip, Vehicle, Driver, CorporateCustomer


class InvoiceServiceTests(TestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Awkward Fleet Operations Pvt Ltd",
            gstin="27AAACA9876A1Z4",
            state_code="27",
        )
        self.fy = FinancialYear.objects.create(
            name="FY 2025-26",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        self.period = FiscalPeriod.objects.create(
            financial_year=self.fy,
            period_number=1,
            name="Apr 2025",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2025, 4, 30),
        )
        self.customer = CorporateCustomer.objects.create(
            code="ACME_TEST",
            legal_name="ACME Logistics Pvt Ltd",
            display_name="ACME Corp",
            gstin="27AAACA1234A1Z5",
            payment_terms_days=30,
        )
        self.vehicle = Vehicle.objects.create(
            registration_number="MH01XY9999",
            make="Toyota",
            model="Camry",
            category="sedan",
            current_city="Mumbai",
            permit_expires_on=datetime.date(2027, 1, 1),
            insurance_expires_on=datetime.date(2027, 1, 1),
            pollution_expires_on=datetime.date(2027, 1, 1),
            fitness_expires_on=datetime.date(2027, 1, 1),
        )
        self.driver = Driver.objects.create(name="Suresh", phone="+919800011122", license_number="DL99887766")

        self.trip1 = Trip.objects.create(
            customer=self.customer,
            pickup_city="Mumbai",
            drop_city="Mumbai",
            pickup_at=datetime.datetime(2026, 7, 23, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 23, 18, 0, tzinfo=datetime.timezone.utc),
            status="COMPLETED",
            vehicle=self.vehicle,
            driver=self.driver,
            fare_amount=Decimal("2400.00"),
        )
        self.closeout1 = TripCloseout.objects.create(
            trip=self.trip1,
            start_odometer_km=1000,
            end_odometer_km=1080,
            status=CloseoutStatus.APPROVED,
        )
        TripCharge.objects.create(
            closeout=self.closeout1,
            category=ChargeCategory.TOLL,
            amount=Decimal("100.00"),
            description="Toll Fee",
        )

    def test_generate_invoice_draft_and_issue(self):
        invoice = InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.subtotal, Decimal("2500.00"))  # 2400 + 100
        self.assertEqual(invoice.cgst_amount, Decimal("62.50"))  # 5% GST total (2.5% CGST = 62.50)
        self.assertEqual(invoice.total_amount, Decimal("2625.00"))

        issued = InvoiceService.issue_invoice(invoice)
        self.assertEqual(issued.status, InvoiceStatus.ISSUED)
        self.assertTrue(issued.invoice_number.startswith("INV/"))

        from billing.models import JournalEntry
        journal = JournalEntry.objects.get(source_id=str(issued.id))
        total_dr = sum(line.debit_amount for line in journal.lines.all())
        total_cr = sum(line.credit_amount for line in journal.lines.all())
        self.assertEqual(total_dr, Decimal("2625.00"))
        self.assertEqual(total_cr, Decimal("2625.00"))


    def test_cannot_invoice_same_trip_twice(self):
        InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])
        with self.assertRaises(ValidationError):
            InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])

    def test_payment_receipt_and_allocation(self):
        from billing.services import PaymentService
        invoice = InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])
        issued = InvoiceService.issue_invoice(invoice)

        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("2625.00"),
            payment_method="BANK_TRANSFER",
            reference_number="NEFT998877",
        )
        self.assertEqual(receipt.unapplied_amount, Decimal("2625.00"))

        allocation = PaymentService.allocate_payment(receipt, issued, Decimal("2625.00"))
        self.assertEqual(receipt.unapplied_amount, Decimal("0.00"))
        self.assertEqual(issued.status, InvoiceStatus.PAID)
        self.assertEqual(issued.balance_amount, Decimal("0.00"))

