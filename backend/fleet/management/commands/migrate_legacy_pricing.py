import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from fleet.models import (
    DutyType,
    PricingAmountStatus,
    RateBook,
    RateBookStatus,
    RateBookType,
    RatePackage,
    Trip,
)
from rentals.models import PackageType, RentalPackage, RentalPricingRule


PACKAGE_DUTY = {
    PackageType.LOCAL: DutyType.LOCAL_8HR_80KM,
    PackageType.AIRPORT: DutyType.AIRPORT_TRANSFER,
    PackageType.OUTSTATION: DutyType.OUTSTATION,
}


class Command(BaseCommand):
    help = "Dry-run or idempotently import legacy rental pricing and report unclassified trip fares."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist imported draft catalogue rows.")
        parser.add_argument("--report", help="Write legacy trip exceptions to this CSV path.")

    @transaction.atomic
    def handle(self, *args, **options):
        apply_changes = options["apply"]
        book, book_created = RateBook.objects.get_or_create(
            source_system="rentals",
            source_id="catalogue",
            defaults={
                "code": "LEGACY-RENTALS",
                "name": "Imported legacy rental catalogue",
                "version": 1,
                "book_type": RateBookType.PUBLIC,
                "status": RateBookStatus.DRAFT,
                "effective_start": timezone.localdate(),
            },
        )
        created = 0
        updated = 0
        rules = RentalPricingRule.objects.select_related("package", "company").order_by("id")
        covered_package_ids = set()
        for rule in rules:
            covered_package_ids.add(rule.package_id)
            _, was_created = self._upsert_rule(book, rule)
            created += int(was_created)
            updated += int(not was_created)
        for package in RentalPackage.objects.exclude(id__in=covered_package_ids).order_by("id"):
            _, was_created = self._upsert_package_default(book, package)
            created += int(was_created)
            updated += int(not was_created)

        legacy_trips = Trip.objects.filter(
            pricing_amount_status=PricingAmountStatus.LEGACY_UNCLASSIFIED
        ).order_by("id")
        exceptions = [
            {
                "trip_id": trip.id,
                "booking_type": trip.booking_type,
                "fare_amount": trip.fare_amount,
                "classification": "LEGACY_UNCLASSIFIED",
                "reason": "No trustworthy historical rate/quote provenance; amount retained unchanged.",
            }
            for trip in legacy_trips
        ]
        if options.get("report"):
            self._write_report(Path(options["report"]), exceptions)
        if not apply_changes:
            transaction.set_rollback(True)
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(
            f"{mode}: rate_book_created={int(book_created)} packages_created={created} "
            f"packages_updated={updated} legacy_trip_exceptions={len(exceptions)}"
        )

    def _upsert_rule(self, book, rule):
        company_code = f"COMPANY-{rule.company_id}" if rule.company_id else "PUBLIC"
        source_id = f"rule:{rule.id}"
        return RatePackage.objects.update_or_create(
            source_system="rentals",
            source_id=source_id,
            defaults={
                "rate_book": book,
                "code": f"RENTAL-{rule.package_id}-{company_code}-{rule.id}",
                "name": f"{rule.package.name} ({company_code})",
                "city": rule.city.strip().lower(),
                "duty_type": PACKAGE_DUTY[rule.package.package_type],
                "included_hours": rule.package.included_hours,
                "included_km": rule.package.included_km,
                "base_rate": rule.base_price,
                "extra_hour_rate": rule.extra_hour_rate,
                "extra_km_rate": rule.extra_km_rate,
                "driver_allowance_per_day": rule.driver_allowance,
            },
        )

    def _upsert_package_default(self, book, package):
        return RatePackage.objects.update_or_create(
            source_system="rentals",
            source_id=f"package:{package.id}",
            defaults={
                "rate_book": book,
                "code": f"RENTAL-{package.id}-DEFAULT",
                "name": package.name,
                "duty_type": PACKAGE_DUTY[package.package_type],
                "included_hours": package.included_hours,
                "included_km": package.included_km,
                "base_rate": package.default_base_price,
                "extra_hour_rate": package.extra_hour_rate,
                "extra_km_rate": package.extra_km_rate,
                "driver_allowance_per_day": package.driver_allowance_per_day,
                "night_charge": package.night_stay_charge,
            },
        )

    def _write_report(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ["trip_id", "booking_type", "fare_amount", "classification", "reason"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
