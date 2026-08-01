import datetime
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from billing.models import (
    LegalEntity,
    FinancialYear,
    FiscalPeriod,
    DocumentSequence,
    DocumentType,
    OTABookingSnapshot,
    OTACounterparty,
    OTASettlementBatch,
    OTASettlementLine,
    OTASettlementStatus,
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
        self.assertFalse(closeout.billing_ready)

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

    def _ota_trip(self, sequence=1):
        from fleet.models import BookingType, PricingAmountStatus, Trip

        return Trip.objects.create(
            booking_type=BookingType.OTA,
            ota_source="MMT",
            ota_external_reference=f"MMT-{sequence}",
            customer_name="OTA Passenger",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=datetime.datetime(2026, 8, sequence, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 8, sequence, 14, 0, tzinfo=datetime.timezone.utc),
            status="completed",
            fare_amount=Decimal("1000.00"),
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("952.38"),
            quoted_tax_amount=Decimal("47.62"),
            quoted_total_amount=Decimal("1000.00"),
            pricing_snapshot={"calculation_version": "ota-test-v1"},
        )

    def _mmt_counterparty(self):
        return OTACounterparty.objects.create(
            code="mmt",
            name="MakeMyTrip",
            payout_beneficiary_name="Index Fleet Operations",
        )

    def _monetary_sources(self, source="MMT_PAID_CALLBACK"):
        return {
            "gross_fare": source,
            "fare_tax": source,
            "commission_amount": source,
            "commission_tax": source,
            "withholding_amount": source,
            "cancellation_amount": source,
            "net_expected": source,
        }

    def test_ota_booking_snapshot_reconciles_expected_net_and_normalizes_counterparty(self):
        counterparty = self._mmt_counterparty()
        self.assertEqual(counterparty.code, "MMT")

        snapshot = OTABookingSnapshot.objects.create(
            trip=self._ota_trip(),
            counterparty=counterparty,
            provider_booking_id="MMT-ORDER-1",
            partner_reference_number="IF-REF-1",
            gross_fare=Decimal("1000.00"),
            fare_tax=Decimal("47.62"),
            commission_rate=Decimal("10.0000"),
            commission_amount=Decimal("100.00"),
            commission_tax=Decimal("18.00"),
            withholding_rate=Decimal("2.0000"),
            withholding_amount=Decimal("20.00"),
            cancellation_amount=Decimal("0.00"),
            net_expected=Decimal("862.00"),
            monetary_sources=self._monetary_sources(),
            source_payload_hash="a" * 64,
        )

        self.assertEqual(snapshot.currency, "INR")
        self.assertEqual(snapshot.settlement_status, OTASettlementStatus.PENDING)

    def test_ota_booking_snapshot_rejects_unreconciled_browser_total(self):
        with self.assertRaisesMessage(ValidationError, "Net expected does not reconcile"):
            OTABookingSnapshot.objects.create(
                trip=self._ota_trip(),
                counterparty=self._mmt_counterparty(),
                provider_booking_id="MMT-ORDER-BAD",
                gross_fare=Decimal("1000.00"),
                fare_tax=Decimal("47.62"),
                commission_amount=Decimal("100.00"),
                commission_tax=Decimal("18.00"),
                withholding_amount=Decimal("20.00"),
                cancellation_amount=Decimal("0.00"),
                net_expected=Decimal("900.00"),
                monetary_sources=self._monetary_sources(),
            )

    def test_ota_booking_snapshot_requires_sources_for_money_fields(self):
        with self.assertRaisesMessage(ValidationError, "Missing monetary sources"):
            OTABookingSnapshot.objects.create(
                trip=self._ota_trip(),
                counterparty=self._mmt_counterparty(),
                provider_booking_id="MMT-ORDER-SOURCE",
                gross_fare=Decimal("1000.00"),
                fare_tax=Decimal("47.62"),
                commission_amount=Decimal("100.00"),
                commission_tax=Decimal("18.00"),
                withholding_amount=Decimal("20.00"),
                cancellation_amount=Decimal("0.00"),
                net_expected=Decimal("862.00"),
                monetary_sources={"gross_fare": "MMT"},
            )

    def test_duplicate_provider_references_do_not_create_duplicate_ota_bookings(self):
        counterparty = self._mmt_counterparty()
        OTABookingSnapshot.objects.create(
            trip=self._ota_trip(1),
            counterparty=counterparty,
            provider_booking_id="MMT-DUPLICATE",
            partner_reference_number="IF-DUPLICATE",
            gross_fare=Decimal("1000.00"),
            fare_tax=Decimal("47.62"),
            commission_amount=Decimal("100.00"),
            commission_tax=Decimal("18.00"),
            withholding_amount=Decimal("20.00"),
            cancellation_amount=Decimal("0.00"),
            net_expected=Decimal("862.00"),
            monetary_sources=self._monetary_sources(),
        )

        with self.assertRaises(ValidationError):
            OTABookingSnapshot.objects.create(
                trip=self._ota_trip(2),
                counterparty=counterparty,
                provider_booking_id="MMT-DUPLICATE",
                partner_reference_number="IF-OTHER",
                gross_fare=Decimal("1000.00"),
                fare_tax=Decimal("47.62"),
                commission_amount=Decimal("100.00"),
                commission_tax=Decimal("18.00"),
                withholding_amount=Decimal("20.00"),
                cancellation_amount=Decimal("0.00"),
                net_expected=Decimal("862.00"),
                monetary_sources=self._monetary_sources(),
            )

    def test_settlement_line_tracks_variance_and_locks_booking_snapshot_money(self):
        counterparty = self._mmt_counterparty()
        snapshot = OTABookingSnapshot.objects.create(
            trip=self._ota_trip(),
            counterparty=counterparty,
            provider_booking_id="MMT-SETTLE-1",
            gross_fare=Decimal("1000.00"),
            fare_tax=Decimal("47.62"),
            commission_amount=Decimal("100.00"),
            commission_tax=Decimal("18.00"),
            withholding_amount=Decimal("20.00"),
            cancellation_amount=Decimal("0.00"),
            net_expected=Decimal("862.00"),
            monetary_sources=self._monetary_sources(),
        )
        batch = OTASettlementBatch.objects.create(
            counterparty=counterparty,
            batch_reference="MMT-BATCH-1",
            net_expected=Decimal("862.00"),
            actual_payout_amount=Decimal("850.00"),
            monetary_sources={"net_expected": "MMT_REMITTANCE", "actual_payout_amount": "BANK_STATEMENT"},
        )
        OTASettlementLine.objects.create(
            batch=batch,
            booking_snapshot=snapshot,
            expected_amount=Decimal("862.00"),
            received_amount=Decimal("850.00"),
            variance_amount=Decimal("-12.00"),
            settlement_status=OTASettlementStatus.EXCEPTION,
            monetary_sources={"expected_amount": "SNAPSHOT", "received_amount": "BANK_STATEMENT"},
        )

        snapshot.gross_fare = Decimal("1001.00")
        snapshot.net_expected = Decimal("863.00")
        with self.assertRaisesMessage(ValidationError, "cannot change financial boundary fields"):
            snapshot.save()

