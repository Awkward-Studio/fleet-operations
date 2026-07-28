import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing.models import CloseoutStatus, TripCloseout
from billing.services import CloseoutService
from fleet.models import MeteringPolicy, Trip, TripStatus


class MeteringPolicyTests(TestCase):
    def closeout(self, policy, **values):
        trip = Trip.objects.create(
            customer_name="Metering customer",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now() - datetime.timedelta(hours=5),
            estimated_drop_at=timezone.now(),
            status=TripStatus.COMPLETED,
            pricing_snapshot={"package": {"metering_policy": policy}},
        )
        defaults = {
            "trip": trip,
            "status": CloseoutStatus.SUBMITTED,
            "start_odometer_km": Decimal("100"),
            "end_odometer_km": Decimal("160"),
            "actual_pickup_at": timezone.now() - datetime.timedelta(hours=4),
            "actual_drop_at": timezone.now(),
        }
        defaults.update(values)
        return TripCloseout.objects.create(**defaults)

    def test_garage_policy_uses_checklist_provenance(self):
        closeout = CloseoutService.derive_actual_quantities(
            self.closeout(MeteringPolicy.GARAGE_TO_GARAGE)
        )
        self.assertEqual(closeout.actual_km, Decimal("60.00"))
        self.assertEqual(closeout.actual_hours, Decimal("4.00"))
        self.assertEqual(closeout.quantity_provenance["odometer_source"], "trip_checklist")

    def test_pickup_to_drop_uses_explicit_milestones_with_timezone(self):
        start = timezone.now() - datetime.timedelta(hours=2, minutes=30)
        end = timezone.now()
        closeout = self.closeout(
            MeteringPolicy.PICKUP_TO_DROP,
            milestone_snapshot={
                "pickup": {"odometer_km": "120", "timestamp": start.isoformat()},
                "drop": {"odometer_km": "150", "timestamp": end.isoformat()},
            },
        )
        CloseoutService.derive_actual_quantities(closeout)
        self.assertEqual(closeout.actual_km, Decimal("30.00"))
        self.assertEqual(closeout.actual_hours, Decimal("2.50"))
        self.assertEqual(closeout.blockers, [])

    def test_missing_pickup_milestones_are_explicit_exceptions(self):
        closeout = CloseoutService.derive_actual_quantities(
            self.closeout(MeteringPolicy.AIRPORT_TRANSFER)
        )
        codes = {item["code"] for item in closeout.blockers}
        self.assertIn("METERING_PICKUP_DROP_ODOMETER_MISSING", codes)
        self.assertIn("METERING_PICKUP_DROP_TIME_MISSING", codes)
        self.assertEqual(closeout.status, CloseoutStatus.EXCEPTION_REVIEW)

    def test_fixed_package_records_usage_without_excess_policy(self):
        closeout = CloseoutService.derive_actual_quantities(
            self.closeout(MeteringPolicy.FIXED_PACKAGE)
        )
        self.assertEqual(closeout.actual_km, Decimal("60.00"))
        self.assertEqual(
            closeout.quantity_provenance["odometer_source"],
            "informational_trip_checklist",
        )
