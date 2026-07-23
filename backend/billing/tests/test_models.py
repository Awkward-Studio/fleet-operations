import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from billing.models import (
    LegalEntity,
    FinancialYear,
    FiscalPeriod,
    DocumentSequence,
    DocumentType,
)


class BillingModelTests(TestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Awkward Fleet Operations Pvt Ltd",
            trade_name="Index Fleet",
            gstin="27AAACA9876A1Z4",
            state_code="27",
            pan="AAACA9876A",
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

    def test_document_sequence_generation(self):
        num1 = DocumentSequence.get_next_number(
            legal_entity=self.entity,
            financial_year=self.fy,
            document_type=DocumentType.INVOICE,
            prefix="INV/25-26/",
        )
        self.assertEqual(num1, "INV/25-26/00001")

        num2 = DocumentSequence.get_next_number(
            legal_entity=self.entity,
            financial_year=self.fy,
            document_type=DocumentType.INVOICE,
            prefix="INV/25-26/",
        )
        self.assertEqual(num2, "INV/25-26/00002")

    def test_financial_year_clean_validation(self):
        invalid_fy = FinancialYear(
            name="Invalid FY",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2025, 4, 1),
        )
        with self.assertRaises(ValidationError):
            invalid_fy.clean()

    def test_trip_closeout_creation(self):
        from fleet.models import Trip, Vehicle, Driver
        vehicle = Vehicle.objects.create(
            registration_number="MH01AB1234",
            make="Toyota",
            model="Camry",
            category="sedan",
            current_city="Mumbai",
            permit_expires_on=datetime.date(2027, 1, 1),
            insurance_expires_on=datetime.date(2027, 1, 1),
            pollution_expires_on=datetime.date(2027, 1, 1),
            fitness_expires_on=datetime.date(2027, 1, 1),
        )
        driver = Driver.objects.create(name="Ramesh", phone="+919876543210", license_number="DL12345678")
        trip = Trip.objects.create(
            pickup_city="Mumbai",
            drop_city="Mumbai",
            pickup_at=datetime.datetime(2026, 7, 23, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 23, 18, 0, tzinfo=datetime.timezone.utc),
            status="COMPLETED",
            vehicle=vehicle,
            driver=driver,
            fare_amount=2500.00,
        )
        from billing.models import TripCloseout, CloseoutStatus, TripCharge, ChargeCategory
        closeout = TripCloseout.objects.create(
            trip=trip,
            start_odometer_km=1000,
            end_odometer_km=1085,
            status=CloseoutStatus.APPROVED,
        )
        self.assertEqual(closeout.actual_km, 85)
        self.assertTrue(closeout.billing_ready)

        charge = TripCharge.objects.create(
            closeout=closeout,
            category=ChargeCategory.TOLL,
            amount=150.00,
            description="Bandra Sealink Toll",
        )
        self.assertEqual(closeout.extra_charges.count(), 1)

    def test_invoice_creation_and_balance(self):
        from billing.models import Invoice, InvoiceStatus, InvoiceLine
        invoice = Invoice.objects.create(
            legal_entity=self.entity,
            financial_year=self.fy,
            fiscal_period=self.period,
            subtotal=2400.00,
            taxable_amount=2400.00,
            cgst_amount=60.00,
            sgst_amount=60.00,
            total_amount=2520.00,
            status=InvoiceStatus.DRAFT,
        )
        self.assertEqual(invoice.balance_amount, 2520.00)

        line = InvoiceLine.objects.create(
            invoice=invoice,
            description="Local 8h/80km Sedan Package",
            unit_rate=2400.00,
            taxable_value=2400.00,
            cgst_rate=2.5,
            cgst_amount=60.00,
            sgst_rate=2.5,
            sgst_amount=60.00,
            line_total=2520.00,
        )
        self.assertEqual(invoice.lines.count(), 1)


