import datetime
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from billing.models import (
    LegalEntity,
    FinancialYear,
    FiscalPeriod,
    InvoiceStatus,
    OTABillingArrangement,
    TripCloseout,
    CloseoutStatus,
    TripCharge,
    ChargeCategory,
)
from billing.services import InvoiceService, OTACommercialService
from fleet.models import (
    BookingType,
    CorporateCustomer,
    Driver,
    PricingAmountStatus,
    Trip,
    Vehicle,
)


class OTACommercialServiceTests(TestCase):
    def test_expected_net_formula_matrix(self):
        scenarios = [
            {
                "gross_fare": Decimal("1000.00"),
                "commission_rate": Decimal("10.00"),
                "commission_tax_rate": Decimal("18.00"),
                "withholding_rate": Decimal("2.00"),
                "adjustments": Decimal("0.00"),
                "expected": Decimal("862.00"),
            },
            {
                "gross_fare": Decimal("1000.00"),
                "commission_amount": Decimal("125.00"),
                "commission_tax_amount": Decimal("22.50"),
                "withholding_amount": Decimal("0.00"),
                "adjustments": Decimal("-50.00"),
                "expected": Decimal("802.50"),
            },
            {
                "gross_fare": Decimal("999.99"),
                "commission_rate": Decimal("12.50"),
                "commission_tax_rate": Decimal("18.00"),
                "withholding_rate": Decimal("1.00"),
                "adjustments": Decimal("10.00"),
                "expected": Decimal("852.49"),
            },
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                result = OTACommercialService.calculate_expected_net(**{
                    key: value for key, value in scenario.items() if key != "expected"
                })
                formula = result["formula_explanation"]
                total = (
                    Decimal(formula["gross_fare"])
                    - Decimal(formula["commission_amount"])
                    - Decimal(formula["commission_tax_amount"])
                    - Decimal(formula["withholding_amount"])
                    + Decimal(formula["adjustments"])
                )
                self.assertEqual(total, scenario["expected"])
                self.assertEqual(Decimal(result["expected_net_settlement"]), scenario["expected"])
                self.assertIsNone(result["exception"])

    def test_unsupported_arrangement_returns_exception_review(self):
        result = OTACommercialService.calculate_expected_net(
            gross_fare=Decimal("1000.00"),
            commission_rate=Decimal("10.00"),
            billing_arrangement=OTABillingArrangement.EXCEPTION_REVIEW,
        )

        self.assertEqual(result["exception"], "UNSUPPORTED_BILLING_ARRANGEMENT")
        self.assertEqual(result["billing_arrangement"], OTABillingArrangement.EXCEPTION_REVIEW)


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
            booking_type=BookingType.CORPORATE,
            pickup_city="Mumbai",
            drop_city="Mumbai",
            pickup_at=datetime.datetime(2026, 7, 23, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 23, 18, 0, tzinfo=datetime.timezone.utc),
            status="completed",
            vehicle=self.vehicle,
            driver=self.driver,
            fare_amount=Decimal("2400.00"),
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("2400.00"),
            quoted_tax_amount=Decimal("120.00"),
            quoted_total_amount=Decimal("2520.00"),
            pricing_snapshot={
                "calculation_version": "contract-quote-v1",
                "itemized_charges": {
                    "cgst_rate": "2.50",
                    "sgst_rate": "2.50",
                },
            },
        )
        self.closeout1 = TripCloseout.objects.create(
            trip=self.trip1,
            start_odometer_km=1000,
            end_odometer_km=1080,
            status=CloseoutStatus.BILLING_READY,
        )
        TripCharge.objects.create(
            closeout=self.closeout1,
            category=ChargeCategory.TOLL,
            amount=Decimal("100.00"),
            description="Toll Fee",
            is_approved=True,
        )

    def test_generate_invoice_draft_and_issue(self):
        invoice = InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertEqual(invoice.customer, self.customer)
        self.assertEqual(invoice.subtotal, Decimal("2500.00"))  # 2400 + 100
        self.assertEqual(invoice.cgst_amount, Decimal("62.50"))  # 5% GST total (2.5% CGST = 62.50)
        self.assertEqual(invoice.total_amount, Decimal("2625.00"))
        trip_line = invoice.lines.get(source_type="TRIP_PRICING")
        self.assertEqual(trip_line.taxable_value, Decimal("2400.00"))
        self.assertEqual(trip_line.source_id, str(self.trip1.id))
        self.assertEqual(trip_line.calculation_version, "contract-quote-v1")
        self.assertEqual(
            trip_line.pricing_snapshot["calculation_version"],
            "contract-quote-v1",
        )

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

    def test_rejects_legacy_unclassified_trip_amount(self):
        self.trip1.pricing_amount_status = PricingAmountStatus.LEGACY_UNCLASSIFIED
        self.trip1.save(update_fields=["pricing_amount_status"])

        with self.assertRaisesMessage(ValidationError, "AMOUNT_UNCLASSIFIED"):
            InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])

    def test_interstate_invoice_posts_igst_liability(self):
        self.customer.gstin = "29AAACA1234A1Z5"
        self.customer.save(update_fields=["gstin"])
        self.trip1.bill_to_gstin_snapshot = self.customer.gstin
        self.trip1.save(update_fields=["bill_to_gstin_snapshot"])

        invoice = InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])
        self.assertEqual(invoice.cgst_amount, Decimal("0.00"))
        self.assertEqual(invoice.sgst_amount, Decimal("0.00"))
        self.assertEqual(invoice.igst_amount, Decimal("125.00"))

        InvoiceService.issue_invoice(invoice)
        from billing.models import JournalEntry

        journal = JournalEntry.objects.get(source_id=str(invoice.id))
        igst_line = journal.lines.get(account__code="2250")
        self.assertEqual(igst_line.credit_amount, Decimal("125.00"))
        self.assertEqual(
            sum(line.debit_amount for line in journal.lines.all()),
            sum(line.credit_amount for line in journal.lines.all()),
        )

    def test_zero_rate_snapshot_produces_no_tax_liability(self):
        self.trip1.pricing_snapshot["itemized_charges"].update(
            {"cgst_rate": "0.00", "sgst_rate": "0.00"}
        )
        self.trip1.quoted_tax_amount = Decimal("0.00")
        self.trip1.quoted_total_amount = Decimal("2400.00")
        self.trip1.save(
            update_fields=[
                "pricing_snapshot",
                "quoted_tax_amount",
                "quoted_total_amount",
            ]
        )

        invoice = InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])
        self.assertEqual(invoice.total_amount, Decimal("2500.00"))
        self.assertEqual(invoice.cgst_amount + invoice.sgst_amount + invoice.igst_amount, Decimal("0.00"))

    def test_adhoc_trip_with_explicit_pricing_is_traceable_and_invoiceable(self):
        adhoc = Trip.objects.create(
            booking_type="ADHOC",
            customer_name="Direct Guest",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=datetime.datetime(2026, 7, 24, 10, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 24, 14, tzinfo=datetime.timezone.utc),
            status="completed",
            fare_amount=Decimal("1575.00"),
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("1500.00"),
            quoted_tax_amount=Decimal("75.00"),
            quoted_total_amount=Decimal("1575.00"),
            pricing_snapshot={
                "calculation_version": "adhoc-quote-v1",
                "itemized_charges": {
                    "cgst_rate": "2.50",
                    "sgst_rate": "2.50",
                },
            },
        )
        TripCloseout.objects.create(
            trip=adhoc,
            start_odometer_km=200,
            end_odometer_km=260,
            status=CloseoutStatus.BILLING_READY,
        )

        invoice = InvoiceService.generate_invoice_draft(self.entity, [adhoc.id])
        line = invoice.lines.get()
        self.assertEqual(invoice.billing_name_snapshot, "Direct Guest")
        self.assertEqual(invoice.total_amount, Decimal("1575.00"))
        self.assertEqual(line.source_id, str(adhoc.id))
        self.assertEqual(line.calculation_version, "adhoc-quote-v1")

    def test_similar_named_direct_customers_never_merge_without_shared_identity(self):
        def create_direct(phone):
            trip = Trip.objects.create(
                booking_type=BookingType.ADHOC,
                customer_name="Rahul Sharma",
                customer_phone=phone,
                pickup_city="Mumbai",
                drop_city="Pune",
                pickup_at=datetime.datetime(2026, 7, 26, 10, tzinfo=datetime.timezone.utc),
                estimated_drop_at=datetime.datetime(2026, 7, 26, 14, tzinfo=datetime.timezone.utc),
                status="completed",
                pricing_amount_status=PricingAmountStatus.QUOTED,
                quoted_taxable_amount=Decimal("1000.00"),
                quoted_tax_amount=Decimal("50.00"),
                quoted_total_amount=Decimal("1050.00"),
                pricing_snapshot={"itemized_charges": {"cgst_rate": "2.50", "sgst_rate": "2.50"}},
            )
            TripCloseout.objects.create(
                trip=trip,
                start_odometer_km=100,
                end_odometer_km=150,
                status=CloseoutStatus.BILLING_READY,
            )
            return trip

        first = create_direct("+919000000001")
        second = create_direct("+919000000002")
        self.assertNotEqual(first.bill_to_key, second.bill_to_key)

        with self.assertRaisesMessage(ValidationError, "BILL_TO_MISMATCH"):
            InvoiceService.generate_invoice_draft(
                self.entity, [first.id, second.id]
            )

    def test_uncompleted_trip_is_rejected_with_status_blocker(self):
        self.trip1.status = "active"
        self.trip1.save(update_fields=["status"])

        with self.assertRaisesMessage(ValidationError, "STATUS_NOT_COMPLETED"):
            InvoiceService.generate_invoice_draft(self.entity, [self.trip1.id])

    def test_same_corporate_bill_to_can_consolidate(self):
        second = Trip.objects.create(
            customer=self.customer,
            booking_type=BookingType.CORPORATE,
            pickup_city="Mumbai",
            drop_city="Nashik",
            pickup_at=datetime.datetime(2026, 7, 27, 10, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 27, 16, tzinfo=datetime.timezone.utc),
            status="completed",
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("1000.00"),
            quoted_tax_amount=Decimal("50.00"),
            quoted_total_amount=Decimal("1050.00"),
            pricing_snapshot={"itemized_charges": {"cgst_rate": "2.50", "sgst_rate": "2.50"}},
        )
        TripCloseout.objects.create(
            trip=second,
            start_odometer_km=1100,
            end_odometer_km=1200,
            status=CloseoutStatus.BILLING_READY,
        )

        invoice = InvoiceService.generate_invoice_draft(
            self.entity, [self.trip1.id, second.id]
        )
        self.assertEqual(invoice.invoice_trips.count(), 2)
        self.assertEqual(invoice.bill_to_key, f"CORPORATE:{self.customer.id}")

    def test_ota_counterparty_groups_separately_from_direct_customer(self):
        def ota_trip(source):
            trip = Trip.objects.create(
                booking_type=BookingType.OTA,
                ota_source=source,
                customer_name="OTA Passenger",
                pickup_city="Mumbai",
                drop_city="Airport",
                pickup_at=datetime.datetime(2026, 7, 28, 10, tzinfo=datetime.timezone.utc),
                estimated_drop_at=datetime.datetime(2026, 7, 28, 12, tzinfo=datetime.timezone.utc),
                status="completed",
                pricing_amount_status=PricingAmountStatus.QUOTED,
                quoted_taxable_amount=Decimal("800.00"),
                quoted_tax_amount=Decimal("40.00"),
                quoted_total_amount=Decimal("840.00"),
                pricing_snapshot={"itemized_charges": {"cgst_rate": "2.50", "sgst_rate": "2.50"}},
            )
            TripCloseout.objects.create(
                trip=trip,
                start_odometer_km=500,
                end_odometer_km=530,
                status=CloseoutStatus.BILLING_READY,
            )
            return trip

        first = ota_trip("MakeMyTrip")
        second = ota_trip("MakeMyTrip")
        invoice = InvoiceService.generate_invoice_draft(
            self.entity, [first.id, second.id]
        )
        self.assertEqual(invoice.bill_to_key, "OTA:MAKEMYTRIP")
        self.assertEqual(invoice.booking_channel, BookingType.OTA)

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
