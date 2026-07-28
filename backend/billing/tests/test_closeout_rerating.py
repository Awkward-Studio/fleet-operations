import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing.models import ChargeCategory, CloseoutStatus, TripCharge, TripCloseout
from billing.services import CloseoutService
from fleet.models import PricingAmountStatus, Trip, TripStatus


RATE_TERMS = {
    "base_rate": "2000.00",
    "included_hours": "8.00",
    "included_km": "80.00",
    "extra_hour_rate": "200.00",
    "extra_km_rate": "15.00",
    "daily_minimum_km": "0.00",
    "waiting_rate_per_hour": "120.00",
    "night_charge": "500.00",
    "driver_allowance_per_day": "300.00",
    "discount_percent": "10.00",
    "cgst_rate": "2.50",
    "sgst_rate": "2.50",
}


class CloseoutReratingTests(TestCase):
    def closeout(self, rate_terms=RATE_TERMS):
        trip = Trip.objects.create(
            customer_name="Actual customer",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now() - datetime.timedelta(hours=10),
            estimated_drop_at=timezone.now(),
            status=TripStatus.COMPLETED,
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("1800"),
            quoted_tax_amount=Decimal("90"),
            quoted_total_amount=Decimal("1890"),
            pricing_snapshot={
                "calculation_version": "unified-rate-card-v1",
                "rate_book": {"id": 4, "version": 2},
                "package": {"id": 8, "duty_type": "LOCAL_8HR_80KM"},
                **({"rate_terms": rate_terms} if rate_terms else {}),
                "total_amount": "1890.00",
            },
        )
        return TripCloseout.objects.create(
            trip=trip,
            status=CloseoutStatus.SUBMITTED,
            actual_km=Decimal("100"),
            actual_hours=Decimal("10"),
            waiting_minutes=30,
            quantity_provenance={"source": "test"},
        )

    def test_rerates_actuals_from_frozen_terms_and_sums_exactly(self):
        closeout = self.closeout()
        TripCharge.objects.create(
            closeout=closeout,
            category=ChargeCategory.TOLL,
            amount=Decimal("100"),
            description="Supported toll",
            is_approved=True,
        )
        result = CloseoutService.rerate_from_original_snapshot(closeout.id)
        # base 2000 + hrs 400 + km 300 + waiting 60 = 2760; discount 276; toll 100 => 2584
        self.assertEqual(result.final_taxable_amount, Decimal("2584.00"))
        self.assertEqual(result.final_tax_amount, Decimal("129.20"))
        self.assertEqual(result.final_total_amount, Decimal("2713.20"))
        self.assertEqual(
            result.final_taxable_amount + result.final_tax_amount,
            result.final_total_amount,
        )
        self.assertEqual(
            result.final_charge_snapshot["original_quote"]["rate_book"]["version"],
            2,
        )

    def test_unapproved_manual_charge_is_excluded(self):
        closeout = self.closeout()
        TripCharge.objects.create(
            closeout=closeout,
            category=ChargeCategory.PARKING,
            amount=Decimal("999"),
            is_approved=False,
        )
        result = CloseoutService.rerate_from_original_snapshot(closeout.id)
        self.assertEqual(result.final_charge_snapshot["manual_components_total"], "0.00")

    def test_missing_original_terms_blocks_instead_of_using_current_rate(self):
        closeout = self.closeout(rate_terms=None)
        result = CloseoutService.rerate_from_original_snapshot(closeout.id)
        self.assertEqual(result.status, CloseoutStatus.EXCEPTION_REVIEW)
        self.assertIsNone(result.final_total_amount)
        self.assertIn(
            "ORIGINAL_RATE_TERMS_MISSING",
            {item["code"] for item in result.blockers},
        )
