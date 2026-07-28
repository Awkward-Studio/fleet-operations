import datetime
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import CloseoutStatus, TripCloseout
from billing.reports import CloseoutReconciliationReport
from fleet.models import Trip, TripStatus


class CloseoutReconciliationReportTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="report-accountant",
            email="report-accountant@example.com",
            role="accountant",
        )
        self.missing = self.trip("Missing", quoted_total_amount=Decimal("0"))
        self.stale = self.trip("Stale", quoted_total_amount=Decimal("1000"))
        self.closeout = TripCloseout.objects.create(
            trip=self.stale,
            status=CloseoutStatus.EXCEPTION_REVIEW,
            quote_variance_percent=Decimal("25"),
        )
        TripCloseout.objects.filter(pk=self.closeout.pk).update(
            updated_at=timezone.now() - datetime.timedelta(hours=72)
        )

    @staticmethod
    def trip(customer, **kwargs):
        return Trip.objects.create(
            customer_name=customer,
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now() + datetime.timedelta(hours=4),
            status=TripStatus.COMPLETED,
            **kwargs,
        )

    def test_counts_reconcile_and_issue_categories_can_overlap(self):
        report = CloseoutReconciliationReport.build()
        self.assertEqual(report["coverage"]["completed_trips"], 2)
        self.assertEqual(report["coverage"]["with_closeout"], 1)
        self.assertEqual(report["coverage"]["missing_closeout"], 1)
        self.assertTrue(report["coverage"]["reconciles"])
        self.assertEqual(report["issue_counts"]["stale_review"], 1)
        self.assertEqual(report["issue_counts"]["large_variance"], 1)
        self.assertEqual(report["issue_counts"]["zero_fare"], 1)

    def test_commercial_endpoint_returns_traceable_rows(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("closeout-reconciliation"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["issues"]["missing_closeout"][0]["trip_id"], self.missing.id)
