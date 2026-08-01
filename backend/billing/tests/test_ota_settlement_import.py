import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import (
    FinancialYear,
    FiscalPeriod,
    JournalEntry,
    LegalEntity,
    CloseoutStatus,
    ExpenseStatus,
    OTAAuditEvent,
    OTABookingSnapshot,
    OTACounterparty,
    OTASettlementBatch,
    OTASettlementLine,
    OTASettlementLineClassification,
    OTASettlementStatus,
    TripCharge,
    TripCloseout,
    TripExpense,
)
from billing.services import OTAProfitabilityReportService, OTASettlementImportService, PostingEngine
from fleet.models import BookingType, PricingAmountStatus, Trip


class OTASettlementImportMixin:
    def setUp(self):
        self.counterparty = OTACounterparty.objects.create(code="MMT", name="MakeMyTrip")

    def _trip(self, ref, sequence=1, status="completed"):
        return Trip.objects.create(
            booking_type=BookingType.OTA,
            ota_source="MMT",
            ota_external_reference=ref,
            customer_name="OTA Passenger",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=datetime.datetime(2026, 8, sequence, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 8, sequence, 14, 0, tzinfo=datetime.timezone.utc),
            status=status,
            fare_amount=Decimal("1000.00"),
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("952.38"),
            quoted_tax_amount=Decimal("47.62"),
            quoted_total_amount=Decimal("1000.00"),
            pricing_snapshot={"calculation_version": "ota-settlement-test-v1"},
        )

    def _snapshot(self, ref, sequence=1, net_expected=Decimal("900.00"), status=OTASettlementStatus.PENDING):
        gross = Decimal("1000.00")
        commission = Decimal("80.00")
        commission_tax = Decimal("14.40")
        withholding = gross - commission - commission_tax - net_expected
        return OTABookingSnapshot.objects.create(
            trip=self._trip(ref, sequence),
            counterparty=self.counterparty,
            provider_booking_id=ref,
            partner_reference_number=f"IF-{ref}",
            currency="INR",
            gross_fare=gross,
            fare_tax=Decimal("47.62"),
            commission_rate=Decimal("8.00"),
            commission_amount=commission,
            commission_tax=commission_tax,
            withholding_rate=Decimal("0.00"),
            withholding_amount=withholding,
            cancellation_amount=Decimal("0.00"),
            net_expected=net_expected,
            settlement_status=status,
            monetary_sources={
                "gross_fare": "TEST",
                "fare_tax": "TEST",
                "commission_amount": "TEST",
                "commission_tax": "TEST",
                "withholding_amount": "TEST",
                "cancellation_amount": "TEST",
                "net_expected": "TEST",
            },
            source_system="TEST",
        )


class OTASettlementImportServiceTests(OTASettlementImportMixin, TestCase):
    def test_import_classifies_exact_short_excess_missing_duplicate_and_cancelled(self):
        self._snapshot("MMT-EXACT", 1)
        self._snapshot("MMT-SHORT", 2)
        self._snapshot("MMT-EXCESS", 3)
        self._snapshot("MMT-CANCEL", 4, status=OTASettlementStatus.CANCELLED)

        result = OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-001",
            currency="INR",
            source_system="API_TEST",
            lines=[
                {"provider_booking_id": "MMT-EXACT", "received_amount": "900.00"},
                {"provider_booking_id": "MMT-SHORT", "received_amount": "850.00"},
                {"provider_booking_id": "MMT-EXCESS", "received_amount": "925.00"},
                {"provider_booking_id": "MMT-MISSING", "received_amount": "700.00"},
                {"provider_booking_id": "MMT-EXACT", "received_amount": "900.00"},
                {"provider_booking_id": "MMT-CANCEL", "received_amount": "900.00"},
            ],
        )

        self.assertEqual(result["status"], OTASettlementStatus.EXCEPTION)
        self.assertEqual(result["classification_counts"][OTASettlementLineClassification.EXACT], 1)
        self.assertEqual(result["classification_counts"][OTASettlementLineClassification.SHORT], 1)
        self.assertEqual(result["classification_counts"][OTASettlementLineClassification.EXCESS], 1)
        self.assertEqual(result["classification_counts"][OTASettlementLineClassification.MISSING], 1)
        self.assertEqual(result["classification_counts"][OTASettlementLineClassification.DUPLICATE], 1)
        self.assertEqual(result["classification_counts"][OTASettlementLineClassification.CANCELLED], 1)
        self.assertEqual(OTASettlementLine.objects.count(), 6)
        self.assertIsNone(
            OTASettlementLine.objects.get(classification=OTASettlementLineClassification.MISSING).booking_snapshot
        )
        self.assertIsNone(
            OTASettlementLine.objects.get(classification=OTASettlementLineClassification.DUPLICATE).booking_snapshot
        )

    def test_rerun_is_idempotent_for_same_batch_reference(self):
        self._snapshot("MMT-RETRY", 1)
        payload = {
            "counterparty_code": "MMT",
            "batch_reference": "SETTLE-RETRY",
            "currency": "INR",
            "lines": [{"provider_booking_id": "MMT-RETRY", "received_amount": "900.00"}],
        }

        first = OTASettlementImportService.import_batch(**payload)
        second = OTASettlementImportService.import_batch(**payload)

        self.assertEqual(first["batch_id"], second["batch_id"])
        self.assertEqual(OTASettlementBatch.objects.count(), 1)
        self.assertEqual(OTASettlementLine.objects.count(), 1)
        self.assertEqual(OTAAuditEvent.objects.filter(entity_id=str(first["batch_id"])).count(), 2)

    def test_failed_rerun_rolls_back_to_previous_lines(self):
        self._snapshot("MMT-ROLLBACK", 1)
        OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-ROLLBACK",
            lines=[{"provider_booking_id": "MMT-ROLLBACK", "received_amount": "900.00"}],
        )

        with self.assertRaises(ValidationError):
            OTASettlementImportService.import_batch(
                counterparty_code="MMT",
                batch_reference="SETTLE-ROLLBACK",
                lines=[{"provider_booking_id": "MMT-ROLLBACK", "received_amount": "-1.00"}],
            )

        self.assertEqual(OTASettlementLine.objects.count(), 1)
        line = OTASettlementLine.objects.get()
        self.assertEqual(line.provider_booking_id, "MMT-ROLLBACK")
        self.assertEqual(line.received_amount, Decimal("900.00"))


class OTASettlementPostingTests(OTASettlementImportMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.legal_entity = LegalEntity.objects.create(
            legal_name="Index Fleet Operations Pvt Ltd",
            gstin="27AAACA9876A1Z4",
            state_code="27",
        )
        self.fy = FinancialYear.objects.create(
            name="FY 2026-27",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
        )
        self.period = FiscalPeriod.objects.create(
            financial_year=self.fy,
            period_number=5,
            name="Aug 2026",
            start_date=datetime.date(2026, 8, 1),
            end_date=datetime.date(2026, 8, 31),
        )

    def _assert_balanced(self, journal):
        self.assertEqual(
            sum(line.debit_amount for line in journal.lines.all()),
            sum(line.credit_amount for line in journal.lines.all()),
        )

    def test_posts_balanced_booking_and_exact_settlement_journals_with_linkage(self):
        snapshot = self._snapshot("MMT-POST", 1)
        OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-POST",
            payout_date=datetime.date(2026, 8, 10),
            lines=[{"provider_booking_id": "MMT-POST", "received_amount": "900.00"}],
        )
        batch = OTASettlementBatch.objects.get(batch_reference="SETTLE-POST")

        journals = PostingEngine.post_ota_settlement_batch(batch)

        self.assertEqual(len(journals), 2)
        for journal in journals:
            self._assert_balanced(journal)
            self.assertEqual(journal.linkage["provider_booking_id"], "MMT-POST")
            self.assertEqual(journal.linkage["trip_id"], snapshot.trip_id)
        booking_journal = JournalEntry.objects.get(source_type="OTA_BOOKING", source_id=str(snapshot.id))
        self.assertTrue(booking_journal.lines.filter(account__code="5200", debit_amount=Decimal("80.00")).exists())
        self.assertTrue(booking_journal.lines.filter(account__code="1200", debit_amount=Decimal("14.40")).exists())
        self.assertTrue(booking_journal.lines.filter(account__code="1110", debit_amount=Decimal("900.00")).exists())
        self.assertTrue(booking_journal.lines.filter(account__code="4000", credit_amount=Decimal("1000.00")).exists())

        reconciliation = PostingEngine.ota_provider_control_reconciliation(
            self.counterparty,
            as_of=datetime.date(2026, 8, 31),
        )
        self.assertEqual(reconciliation["ota_settlement_receivable"], "0.00")
        self.assertEqual(reconciliation["unmatched_ota_cash"], "0.00")

    def test_short_settlement_posts_variance_and_clears_provider_receivable(self):
        self._snapshot("MMT-SHORT-POST", 1)
        OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-SHORT-POST",
            payout_date=datetime.date(2026, 8, 10),
            lines=[{"provider_booking_id": "MMT-SHORT-POST", "received_amount": "850.00"}],
        )
        batch = OTASettlementBatch.objects.get(batch_reference="SETTLE-SHORT-POST")

        PostingEngine.post_ota_settlement_batch(batch)

        settlement_journal = JournalEntry.objects.get(source_type="OTA_SETTLEMENT_LINE")
        self._assert_balanced(settlement_journal)
        self.assertTrue(settlement_journal.lines.filter(account__code="5220", debit_amount=Decimal("50.00")).exists())
        reconciliation = PostingEngine.ota_provider_control_reconciliation(
            self.counterparty,
            as_of=datetime.date(2026, 8, 31),
        )
        self.assertEqual(reconciliation["ota_settlement_receivable"], "0.00")

    def test_missing_cash_posts_to_unmatched_liability(self):
        OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-MISSING-POST",
            payout_date=datetime.date(2026, 8, 10),
            lines=[{"provider_booking_id": "MMT-UNKNOWN", "received_amount": "700.00"}],
        )
        batch = OTASettlementBatch.objects.get(batch_reference="SETTLE-MISSING-POST")

        PostingEngine.post_ota_settlement_batch(batch)

        settlement_journal = JournalEntry.objects.get(source_type="OTA_SETTLEMENT_LINE")
        self._assert_balanced(settlement_journal)
        self.assertTrue(settlement_journal.lines.filter(account__code="2350", credit_amount=Decimal("700.00")).exists())
        reconciliation = PostingEngine.ota_provider_control_reconciliation(
            self.counterparty,
            as_of=datetime.date(2026, 8, 31),
        )
        self.assertEqual(reconciliation["unmatched_ota_cash"], "-700.00")

    def test_reversal_retains_original_linkage(self):
        self._snapshot("MMT-REV", 1)
        OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-REV",
            payout_date=datetime.date(2026, 8, 10),
            lines=[{"provider_booking_id": "MMT-REV", "received_amount": "900.00"}],
        )
        batch = OTASettlementBatch.objects.get(batch_reference="SETTLE-REV")
        original = PostingEngine.post_ota_settlement_batch(batch)[1]

        reversal = PostingEngine.post_ota_journal_reversal(original, reason="Provider statement voided")

        self._assert_balanced(reversal)
        self.assertEqual(reversal.linkage["reverses_journal_entry_id"], original.id)
        self.assertEqual(reversal.linkage["provider_booking_id"], "MMT-REV")
        self.assertTrue(
            reversal.lines.filter(
                linkage__reverses_journal_line_id__isnull=False,
            ).exists()
        )

    def test_profitability_report_uses_approved_costs_and_flags_incomplete_margin(self):
        snapshot = self._snapshot("MMT-MARGIN", 1)
        closeout = TripCloseout.objects.create(
            trip=snapshot.trip,
            start_odometer_km=100,
            end_odometer_km=180,
            status=CloseoutStatus.SUBMITTED,
        )
        TripCharge.objects.create(
            closeout=closeout,
            category="TOLL",
            amount=Decimal("50.00"),
            description="Unapproved toll",
        )
        TripCharge.objects.create(
            closeout=closeout,
            category="PARKING",
            amount=Decimal("25.00"),
            description="Approved parking",
            is_approved=True,
        )
        TripExpense.objects.create(
            trip=snapshot.trip,
            category="FUEL",
            amount=Decimal("100.00"),
            status=ExpenseStatus.APPROVED,
        )
        TripExpense.objects.create(
            trip=snapshot.trip,
            category="MISC",
            amount=Decimal("40.00"),
            status=ExpenseStatus.SUBMITTED,
        )
        OTASettlementImportService.import_batch(
            counterparty_code="MMT",
            batch_reference="SETTLE-MARGIN",
            payout_date=datetime.date(2026, 8, 10),
            lines=[{"provider_booking_id": "MMT-MARGIN", "received_amount": "900.00"}],
        )

        report = OTAProfitabilityReportService.build(counterparty_code="MMT")

        row = report["results"][0]
        self.assertEqual(row["profitability"]["approved_expenses"], "100.00")
        self.assertEqual(row["profitability"]["approved_closeout_charges"], "25.00")
        self.assertEqual(row["profitability"]["approved_costs"], "125.00")
        self.assertEqual(row["profitability"]["contribution_margin"], "775.00")
        self.assertTrue(row["profitability"]["margin_incomplete"])
        self.assertIn("PENDING_EXPENSE_REVIEW", row["profitability"]["incomplete_reasons"])


class OTASettlementImportAPITests(OTASettlementImportMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="settlement_admin",
            email="settlement@indexfleet.com",
            password="password123",
            role="accountant",
        )
        self.client.force_authenticate(self.user)

    def test_import_batch_api(self):
        self._snapshot("MMT-API", 1)

        response = self.client.post(
            "/api/billing/ota-settlements/import_batch/",
            {
                "counterparty_code": "MMT",
                "batch_reference": "SETTLE-API",
                "currency": "INR",
                "lines": [{"provider_booking_id": "MMT-API", "received_amount": "900.00"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["classification_counts"][OTASettlementLineClassification.EXACT], 1)
        self.assertEqual(OTASettlementBatch.objects.get().settlement_status, OTASettlementStatus.SETTLED)

    def test_profitability_report_api(self):
        self._snapshot("MMT-REPORT", 1)

        response = self.client.get("/api/billing/ota-settlements/profitability/?counterparty=MMT")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["trip_count"], 1)
        self.assertEqual(response.data["results"][0]["external"]["provider_booking_id"], "MMT-REPORT")
