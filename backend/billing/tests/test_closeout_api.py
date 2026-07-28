import datetime
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import CloseoutStatus, FinancialYear, Invoice, InvoiceTrip, LegalEntity, TripCloseout
from fleet.models import PricingAmountStatus, Trip, TripStatus


RATE_TERMS = {
    "base_rate": "2000.00",
    "included_hours": "8.00",
    "included_km": "80.00",
    "extra_hour_rate": "200.00",
    "extra_km_rate": "15.00",
    "daily_minimum_km": "0.00",
    "waiting_rate_per_hour": "100.00",
    "night_charge": "0.00",
    "driver_allowance_per_day": "0.00",
    "discount_percent": "0.00",
    "cgst_rate": "2.50",
    "sgst_rate": "2.50",
}


class CloseoutLifecycleAPITests(APITestCase):
    def setUp(self):
        self.dispatcher = User.objects.create_user(
            username="closeout-dispatch",
            email="closeout-dispatch@example.com",
            role="dispatcher",
        )
        self.accountant = User.objects.create_user(
            username="closeout-accountant",
            email="closeout-accountant@example.com",
            role="accountant",
        )
        self.other_accountant = User.objects.create_user(
            username="closeout-reviewer",
            email="closeout-reviewer@example.com",
            role="accountant",
        )
        self.trip = Trip.objects.create(
            customer_name="Closeout API",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now() - datetime.timedelta(hours=10),
            estimated_drop_at=timezone.now(),
            status=TripStatus.COMPLETED,
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("2000"),
            quoted_tax_amount=Decimal("100"),
            quoted_total_amount=Decimal("2100"),
            pricing_snapshot={
                "calculation_version": "unified-rate-card-v1",
                "package": {"duty_type": "LOCAL_8HR_80KM", "metering_policy": "GARAGE_TO_GARAGE"},
                "rate_book": {"version": 1},
                "rate_terms": RATE_TERMS,
                "total_amount": "2100.00",
            },
        )
        self.closeout = TripCloseout.objects.create(
            trip=self.trip,
            status=CloseoutStatus.INCOMPLETE,
            start_odometer_km=100,
            end_odometer_km=180,
            actual_pickup_at=timezone.now() - datetime.timedelta(hours=8),
            actual_drop_at=timezone.now(),
        )

    def post(self, action, user, data=None):
        self.client.force_authenticate(user)
        return self.client.post(
            reverse(f"closeout-{action}", args=[self.closeout.id]),
            data or {},
            format="json",
        )

    def test_submit_approve_and_mark_ready_freezes_trip_final_amount(self):
        submitted = self.post("submit", self.dispatcher)
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.assertEqual(submitted.data["status"], CloseoutStatus.SUBMITTED)
        approved = self.post("approve", self.accountant)
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertFalse(approved.data["billing_ready"])
        ready = self.post("mark-billing-ready", self.accountant)
        self.assertEqual(ready.status_code, status.HTTP_200_OK)
        self.assertTrue(ready.data["billing_ready"])
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.pricing_amount_status, PricingAmountStatus.FINALIZED)
        self.assertEqual(self.trip.final_total_amount, Decimal("2100.00"))
        actions = [item["action"] for item in ready.data["audit_events"]]
        self.assertEqual(actions, ["SUBMIT", "APPROVE", "MARK_BILLING_READY"])

    def test_submitter_cannot_self_approve(self):
        self.client.force_authenticate(self.accountant)
        self.client.post(reverse("closeout-submit", args=[self.closeout.id]))
        response = self.client.post(reverse("closeout-approve", args=[self.closeout.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_return_and_reopen_require_reason(self):
        self.post("submit", self.dispatcher)
        missing = self.post("return-for-changes", self.accountant)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        returned = self.post("return-for-changes", self.accountant, {"reason": "Check waiting evidence"})
        self.assertEqual(returned.status_code, status.HTTP_200_OK)
        self.assertEqual(returned.data["status"], CloseoutStatus.REOPENED)

    def test_invoiced_closeout_cannot_reopen(self):
        self.post("submit", self.dispatcher)
        self.post("approve", self.accountant)
        self.post("mark-billing-ready", self.accountant)
        entity = LegalEntity.objects.create(legal_name="Fleet", gstin="27ABCDE1234F1Z5", state_code="27")
        fy = FinancialYear.objects.create(
            name="FY closeout",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2027, 3, 31),
        )
        invoice = Invoice.objects.create(legal_entity=entity, financial_year=fy)
        InvoiceTrip.objects.create(invoice=invoice, trip=self.trip)
        response = self.post("reopen", self.accountant, {"reason": "Correction"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_dispatcher_cannot_approve(self):
        self.post("submit", self.dispatcher)
        response = self.post("approve", self.dispatcher)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
