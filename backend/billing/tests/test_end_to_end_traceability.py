import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing.models import (
    CloseoutStatus,
    FinancialYear,
    InvoiceStatus,
    JournalEntry,
    LegalEntity,
    TripCloseout,
)
from billing.services import InvoiceService
from fleet.models import BookingType, CorporateCustomer, PricingAmountStatus, Trip


class BillingTraceabilityScenarioTests(TestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Trace Fleet",
            gstin="27ABCDE1234F1Z5",
            state_code="27",
        )
        FinancialYear.objects.create(
            name="FY trace",
            start_date=datetime.date.today() - datetime.timedelta(days=30),
            end_date=datetime.date.today() + datetime.timedelta(days=335),
        )
        self.customer = CorporateCustomer.objects.create(
            code="TRACE",
            legal_name="Trace Corporate",
            display_name="Trace Corporate",
            billing_email="finance@trace.example",
        )

    def trip(self, booking_type, sequence, customer=None, ota_source=""):
        trip = Trip.objects.create(
            customer=customer,
            booking_type=booking_type,
            customer_name=f"{booking_type} Customer",
            customer_phone=f"+9191000000{sequence:02d}",
            ota_source=ota_source,
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now() + datetime.timedelta(hours=4),
            status="completed",
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("1000.00"),
            quoted_tax_amount=Decimal("50.00"),
            quoted_total_amount=Decimal("1050.00"),
            pricing_snapshot={
                "calculation_version": "trace-v1",
                "itemized_charges": {"cgst_rate": "2.50", "sgst_rate": "2.50"},
            },
        )
        TripCloseout.objects.create(
            trip=trip,
            start_odometer_km=100,
            end_odometer_km=150,
            status=CloseoutStatus.BILLING_READY,
        )
        return trip

    def issue(self, trips):
        invoice = InvoiceService.generate_invoice_draft(
            self.entity, [trip.id for trip in trips]
        )
        invoice.status = InvoiceStatus.APPROVED
        invoice.save(update_fields=["status"])
        return InvoiceService.issue_invoice(invoice)

    def test_channel_matrix_and_corporate_consolidation_reconcile_to_journal(self):
        scenarios = [
            [
                self.trip(BookingType.CORPORATE, 1, customer=self.customer),
                self.trip(BookingType.CORPORATE, 2, customer=self.customer),
            ],
            [self.trip(BookingType.ADHOC, 3)],
            [self.trip(BookingType.OTA, 4, ota_source="MakeMyTrip")],
        ]
        for trips in scenarios:
            invoice = self.issue(trips)
            self.assertEqual(invoice.invoice_trips.count(), len(trips))
            self.assertEqual(invoice.lines.count(), len(trips))
            self.assertEqual(invoice.total_amount, Decimal("1050.00") * len(trips))
            journal = JournalEntry.objects.get(
                source_type="INVOICE", source_id=str(invoice.id)
            )
            debit = sum(line.debit_amount for line in journal.lines.all())
            credit = sum(line.credit_amount for line in journal.lines.all())
            self.assertEqual(debit, invoice.total_amount)
            self.assertEqual(credit, invoice.total_amount)
