import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from billing.models import CloseoutStatus, TripCloseout
from billing.services import CloseoutService
from fleet.models import Trip, TripChecklist, TripStatus
from media_store.models import UploadedAsset


class CloseoutCreationTests(TestCase):
    def asset(self, name):
        return UploadedAsset.objects.create(
            kind=UploadedAsset.KIND_IMAGE,
            file_url=f"/private/{name}.jpg",
            original_name=f"{name}.jpg",
            content_type="image/jpeg",
        )

    def trip(self, status=TripStatus.COMPLETED):
        return Trip.objects.create(
            customer_name="Closeout customer",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now() - datetime.timedelta(hours=4),
            estimated_drop_at=timezone.now(),
            status=status,
        )

    def test_completed_trip_creates_exactly_one_closeout(self):
        trip = self.trip()
        TripChecklist.objects.create(
            trip=trip,
            start_odometer_km=100,
            end_odometer_km=145,
            start_odometer_asset=self.asset("start"),
            end_odometer_asset=self.asset("end"),
        )
        first = CloseoutService.create_from_trip_completion(trip.id, "complete:1")
        second = CloseoutService.create_from_trip_completion(trip.id, "complete:1")
        self.assertEqual(first.id, second.id)
        self.assertEqual(TripCloseout.objects.filter(trip=trip).count(), 1)
        self.assertEqual(first.status, CloseoutStatus.SUBMITTED)
        self.assertEqual(first.actual_km, 45)
        self.assertEqual(first.blockers, [])

    def test_missing_evidence_is_a_blocker_not_a_guess(self):
        trip = self.trip()
        closeout = CloseoutService.create_from_trip_completion(trip.id, "complete:missing")
        self.assertEqual(closeout.status, CloseoutStatus.EXCEPTION_REVIEW)
        self.assertEqual(closeout.actual_km, 0)
        self.assertEqual(closeout.blockers[0]["code"], "CHECKLIST_MISSING")

    def test_incomplete_trip_is_rejected(self):
        trip = self.trip(status=TripStatus.ACTIVE)
        with self.assertRaises(ValidationError):
            CloseoutService.create_from_trip_completion(trip.id, "complete:invalid")

    def test_completed_trip_with_rate_terms_calculates_price_automatically(self):
        trip = self.trip()
        trip.pricing_snapshot = {
            "rate_terms": {
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
        }
        trip.save()
        TripChecklist.objects.create(
            trip=trip,
            start_odometer_km=100,
            end_odometer_km=145,
            start_odometer_asset=self.asset("start"),
            end_odometer_asset=self.asset("end"),
        )
        closeout = CloseoutService.create_from_trip_completion(trip.id, "complete:rate_terms")
        self.assertEqual(closeout.status, CloseoutStatus.SUBMITTED)
        self.assertEqual(closeout.actual_km, 45)
        self.assertEqual(closeout.final_taxable_amount, Decimal("1800.00"))
        self.assertEqual(closeout.final_tax_amount, Decimal("90.00"))
        self.assertEqual(closeout.final_total_amount, Decimal("1890.00"))
