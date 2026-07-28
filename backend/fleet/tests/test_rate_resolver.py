import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fleet.models import (
    ContractStatus,
    CorporateContract,
    CorporateCustomer,
    DutyType,
    RateBook,
    RateBookStatus,
    RateBookType,
    RatePackage,
)
from fleet.rate_resolver import AmbiguousRateError, RateResolutionError, resolve_rate


class RateResolverTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="approver")
        self.customer = CorporateCustomer.objects.create(
            code="RESOLVE",
            legal_name="Resolve Ltd",
            display_name="Resolve",
        )
        self.contract = CorporateContract.objects.create(
            customer=self.customer,
            title="Resolver contract",
            effective_start=datetime.date(2026, 1, 1),
            status=ContractStatus.ACTIVE,
        )
        approved_at = timezone.now()
        self.public = RateBook.objects.create(
            code="PUBLIC",
            name="Public",
            version=1,
            book_type=RateBookType.PUBLIC,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
            approved_by=user,
            approved_at=approved_at,
        )
        self.corporate = RateBook.objects.create(
            code="CORP",
            name="Corporate",
            version=1,
            book_type=RateBookType.CORPORATE,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
            contract=self.contract,
            approved_by=user,
            approved_at=approved_at,
        )
        self.ota = RateBook.objects.create(
            code="OTA-UBER",
            name="Uber",
            version=1,
            book_type=RateBookType.OTA,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
            ota_source="UBER",
            approved_by=user,
            approved_at=approved_at,
        )
        self.public_wildcard = self.package(self.public, "PUBLIC-DEFAULT")
        self.public_city = self.package(self.public, "PUBLIC-MUMBAI", city="mumbai")
        self.corporate_city = self.package(self.corporate, "CORP-MUMBAI", city="mumbai")
        self.ota_city = self.package(self.ota, "OTA-MUMBAI", city="mumbai")

    def package(self, book, code, **scope):
        return RatePackage.objects.create(
            rate_book=book,
            code=code,
            name=code,
            duty_type=DutyType.LOCAL_8HR_80KM,
            vehicle_category=scope.pop("vehicle_category", "sedan"),
            base_rate=Decimal("1000.00"),
            **scope,
        )

    def resolve(self, **overrides):
        values = {
            "booking_type": "ADHOC",
            "pickup_datetime": "2026-07-28T10:00:00",
            "pickup_city": "Mumbai",
            "drop_city": "Pune",
            "vehicle_category": "Sedan",
            "duty_type": DutyType.LOCAL_8HR_80KM,
        }
        values.update(overrides)
        return resolve_rate(**values)

    def test_corporate_override_beats_public_city(self):
        result = self.resolve(booking_type="CORPORATE", contract_id=self.contract.id)
        self.assertEqual(result.package, self.corporate_city)
        self.assertEqual(result.trace[0]["channel"], RateBookType.CORPORATE)

    def test_ota_beats_public_and_public_city_beats_wildcard(self):
        self.assertEqual(self.resolve(booking_type="OTA", ota_source="uber").package, self.ota_city)
        public_result = self.resolve()
        self.assertEqual(public_result.package, self.public_city)
        self.assertGreater(len(public_result.trace), 1)

    def test_same_inputs_are_deterministic(self):
        first = self.resolve().as_dict()
        second = self.resolve().as_dict()
        self.assertEqual(first, second)

    def test_equal_precedence_is_rejected(self):
        competing_book = RateBook.objects.create(
            code="PUBLIC-SECOND",
            name="Public second",
            version=1,
            book_type=RateBookType.PUBLIC,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
        )
        self.package(competing_book, "SECOND-MUMBAI", city="mumbai")
        with self.assertRaises(AmbiguousRateError):
            self.resolve()

    def test_missing_rate_is_explicit(self):
        with self.assertRaises(RateResolutionError):
            self.resolve(vehicle_category="Bus")
