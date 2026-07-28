import datetime
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from fleet.models import RateBook, RatePackage, Trip
from rentals.models import RentalPackage, RentalPricingRule


class LegacyPricingMigrationTests(TestCase):
    def setUp(self):
        package = RentalPackage.objects.create(
            name="Local legacy",
            included_hours=8,
            included_km=80,
            default_base_price=Decimal("2000"),
            extra_hour_rate=Decimal("200"),
            extra_km_rate=Decimal("15"),
        )
        RentalPricingRule.objects.create(
            package=package,
            city="Mumbai",
            base_price=Decimal("2200"),
            extra_hour_rate=Decimal("220"),
            extra_km_rate=Decimal("16"),
            driver_allowance=Decimal("300"),
        )
        Trip.objects.create(
            customer_name="Historical",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now() + datetime.timedelta(hours=4),
            fare_amount=Decimal("3000"),
        )

    def test_dry_run_rolls_back_and_reports_counts(self):
        output = StringIO()
        call_command("migrate_legacy_pricing", stdout=output)
        self.assertIn("DRY-RUN", output.getvalue())
        self.assertIn("legacy_trip_exceptions=1", output.getvalue())
        self.assertFalse(RateBook.objects.exists())

    def test_apply_is_idempotent_and_writes_exception_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "exceptions.csv"
            call_command("migrate_legacy_pricing", "--apply", "--report", str(report))
            call_command("migrate_legacy_pricing", "--apply", "--report", str(report))
            self.assertEqual(RateBook.objects.count(), 1)
            self.assertEqual(RatePackage.objects.count(), 1)
            self.assertIn("LEGACY_UNCLASSIFIED", report.read_text())
            trip = Trip.objects.get()
            self.assertEqual(trip.fare_amount, Decimal("3000"))
