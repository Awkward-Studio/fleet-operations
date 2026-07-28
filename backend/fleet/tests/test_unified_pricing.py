import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from fleet.models import DutyType, RateBook, RateBookStatus, RateBookType, RatePackage
from fleet.pricing_service import PricingError, calculate_package_quote, calculate_unified_quote


class UnifiedPricingTests(TestCase):
    def setUp(self):
        self.book = RateBook.objects.create(
            code="PUBLIC-QUOTE",
            name="Public quote",
            version=3,
            book_type=RateBookType.PUBLIC,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
            approved_at=timezone.now(),
        )

    def package(self, duty_type=DutyType.LOCAL_8HR_80KM, **values):
        defaults = {
            "rate_book": self.book,
            "code": duty_type,
            "name": duty_type,
            "city": "mumbai",
            "vehicle_category": "sedan",
            "duty_type": duty_type,
            "included_hours": Decimal("8"),
            "included_km": Decimal("80"),
            "base_rate": Decimal("2000"),
            "extra_hour_rate": Decimal("200"),
            "extra_km_rate": Decimal("15"),
            "waiting_rate_per_hour": Decimal("100"),
            "night_charge": Decimal("500"),
            "driver_allowance_per_day": Decimal("300"),
            "discount_percent": Decimal("10"),
            "cgst_rate": Decimal("2.5"),
            "sgst_rate": Decimal("2.5"),
        }
        defaults.update(values)
        return RatePackage.objects.create(**defaults)

    def test_itemized_decimal_quote(self):
        quote = calculate_package_quote(
            self.package(),
            planned_hours=10,
            planned_km=100,
            waiting_hours=1,
            night_charge_count=1,
            driver_allowance_days=1,
        )
        self.assertEqual(quote["pre_discount_amount"], "3600.00")
        self.assertEqual(quote["discount_amount"], "360.00")
        self.assertEqual(quote["taxable_amount"], "3240.00")
        self.assertEqual(quote["tax_amount"], "162.00")
        self.assertEqual(quote["total_amount"], "3402.00")

    def test_outstation_daily_base_and_minimum(self):
        package = self.package(
            duty_type=DutyType.OUTSTATION,
            code="OUTSTATION",
            included_hours=Decimal("24"),
            included_km=Decimal("250"),
            daily_minimum_km=Decimal("300"),
            discount_percent=Decimal("0"),
        )
        quote = calculate_package_quote(package, planned_km=400, outstation_days=2)
        self.assertEqual(quote["itemized_charges"]["base_charge"], "4000.00")
        self.assertEqual(quote["inputs"]["effective_km"], "600")
        self.assertEqual(quote["usage"]["excess_km"], "100")

    def test_unified_quote_resolves_and_snapshots_trace(self):
        package = self.package()
        quote = calculate_unified_quote(
            booking_type="ADHOC",
            pickup_datetime="2026-07-28T10:00:00",
            pickup_city="Mumbai",
            drop_city="Pune",
            vehicle_category="Sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            planned_hours=8,
            planned_km=80,
        )
        self.assertEqual(quote["package"]["id"], package.id)
        self.assertEqual(quote["rate_book"]["version"], 3)
        self.assertTrue(quote["resolution"]["trace"][0]["selected"])

    def test_negative_usage_is_rejected(self):
        with self.assertRaises(PricingError):
            calculate_package_quote(self.package(), planned_km=-1)

    def test_ota_gross_to_net_reconciliation_and_missing_terms(self):
        ota_book = RateBook.objects.create(
            code="OTA-QUOTE",
            name="OTA",
            version=1,
            book_type=RateBookType.OTA,
            status=RateBookStatus.ACTIVE,
            ota_source="MMT",
            effective_start=datetime.date(2026, 1, 1),
            approved_at=timezone.now(),
        )
        ota_package = RatePackage.objects.create(
            rate_book=ota_book,
            code="OTA-LOCAL",
            name="OTA local",
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            base_rate=Decimal("1000"),
            cgst_rate=Decimal("0"),
            sgst_rate=Decimal("0"),
        )
        with self.assertRaisesMessage(PricingError, "settlement terms are missing"):
            calculate_package_quote(ota_package)
        ota_package.ota_terms_configured = True
        ota_package.ota_commission_rate = Decimal("20")
        ota_package.ota_withholding_rate = Decimal("1")
        ota_package.save()
        commercial = calculate_package_quote(ota_package)["ota_commercial"]
        self.assertEqual(commercial["gross_customer_fare"], "1000.00")
        self.assertEqual(commercial["commission_amount"], "200.00")
        self.assertEqual(commercial["withholding_amount"], "10.00")
        self.assertEqual(commercial["expected_net_settlement"], "790.00")
