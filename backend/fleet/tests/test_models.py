from decimal import Decimal
import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from fleet.models import (
    CorporateCustomer,
    CustomerContact,
    CorporateContract,
    ContractRate,
    ContractAllowance,
    CustomerStatus,
    ContactType,
    ContractStatus,
    DutyType,
    AllowanceType,
    MeteringPolicy,
    RateBook,
    RateBookStatus,
    RateBookType,
    RatePackage,
    QuoteOverrideStatus,
    Trip,
    TripQuoteOverride,
)


class FleetModelTests(TestCase):
    def setUp(self):
        self.customer = CorporateCustomer.objects.create(
            code="ACME01",
            legal_name="ACME Logistics Private Limited",
            display_name="ACME Corp",
            status=CustomerStatus.ACTIVE,
            gstin="27AAAAA0000A1Z5",
            payment_terms_days=30,
        )

    def test_customer_creation_and_cleaning(self):
        customer = CorporateCustomer(
            code=" test02 ",
            legal_name="Test Legal",
            display_name="Test Display",
        )
        customer.clean()
        self.assertEqual(customer.code, "TEST02")
        customer.save()
        self.assertEqual(str(customer), "Test Display (TEST02)")

    def test_customer_contact_creation(self):
        contact = CustomerContact.objects.create(
            customer=self.customer,
            name="John Doe",
            contact_type=ContactType.PRIMARY,
            email="john@acme.com",
            phone="9876543210",
            is_primary=True,
        )
        self.assertEqual(str(contact), "John Doe - ACME Corp (PRIMARY)")

    def test_contract_validation(self):
        start = datetime.date(2026, 1, 1)
        end = datetime.date(2025, 12, 31)
        contract = CorporateContract(
            customer=self.customer,
            title="Master Services Agreement 2026",
            effective_start=start,
            effective_end=end,
            cgst_rate=Decimal("2.50"),
            sgst_rate=Decimal("2.50"),
        )
        with self.assertRaises(ValidationError):
            contract.full_clean()

    def test_contract_rate_uniqueness(self):
        contract = CorporateContract.objects.create(
            customer=self.customer,
            title="MSA 2026",
            effective_start=datetime.date(2026, 1, 1),
            effective_end=datetime.date(2026, 12, 31),
            status=ContractStatus.ACTIVE,
        )
        ContractRate.objects.create(
            contract=contract,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            included_hours=8,
            included_km=80,
            base_rate=Decimal("2500.00"),
        )
        with self.assertRaises(IntegrityError):
            ContractRate.objects.create(
                contract=contract,
                city="mumbai",
                vehicle_category="sedan",
                duty_type=DutyType.LOCAL_8HR_80KM,
                included_hours=8,
                included_km=80,
                base_rate=Decimal("3000.00"),
            )

    def test_contract_allowance_uniqueness(self):
        contract = CorporateContract.objects.create(
            customer=self.customer,
            title="MSA 2026",
            effective_start=datetime.date(2026, 1, 1),
            effective_end=datetime.date(2026, 12, 31),
            status=ContractStatus.ACTIVE,
        )
        ContractAllowance.objects.create(
            contract=contract,
            allowance_type=AllowanceType.OVERTIME_PER_HOUR,
            amount=Decimal("150.00"),
        )
        with self.assertRaises(IntegrityError):
            ContractAllowance.objects.create(
                contract=contract,
                allowance_type=AllowanceType.OVERTIME_PER_HOUR,
                amount=Decimal("200.00"),
            )

    def test_rate_book_requires_channel_applicability(self):
        rate_book = RateBook(
            code="corp-2026",
            name="Corporate 2026",
            version=1,
            book_type=RateBookType.CORPORATE,
            effective_start=datetime.date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError):
            rate_book.full_clean()

    def test_active_rate_book_scope_is_unambiguous_and_source_is_resolvable(self):
        contract = CorporateContract.objects.create(
            customer=self.customer,
            title="MSA 2026",
            effective_start=datetime.date(2026, 1, 1),
            status=ContractStatus.ACTIVE,
        )
        values = {
            "code": "CORP-2026",
            "name": "Corporate 2026",
            "book_type": RateBookType.CORPORATE,
            "status": RateBookStatus.ACTIVE,
            "effective_start": datetime.date(2026, 1, 1),
            "contract": contract,
            "approved_at": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        }
        RateBook.objects.create(version=1, source_system="contract", source_id=str(contract.id), **values)
        with self.assertRaises(IntegrityError):
            RateBook.objects.create(version=2, code="CORP-2027", **{k: v for k, v in values.items() if k != "code"})

    def test_rate_package_scope_and_decimal_validation(self):
        book = RateBook.objects.create(
            code="PUBLIC",
            name="Public",
            version=1,
            book_type=RateBookType.PUBLIC,
            effective_start=datetime.date(2026, 1, 1),
        )
        package = RatePackage(
            rate_book=book,
            code="local-8-80",
            name="Local 8h / 80km",
            city=" Mumbai ",
            vehicle_category=" Sedan ",
            duty_type=DutyType.LOCAL_8HR_80KM,
            included_hours=Decimal("8"),
            included_km=Decimal("80"),
            base_rate=Decimal("2500"),
        )
        package.full_clean()
        package.save()
        self.assertEqual(package.city, "mumbai")
        self.assertEqual(package.vehicle_category, "sedan")

    def test_quote_override_preserves_delta_and_separation_of_duties(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        requester = get_user_model().objects.create_user(username="override-requester")
        trip = Trip.objects.create(
            customer_name="Direct customer",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now() + datetime.timedelta(hours=3),
        )
        override = TripQuoteOverride.objects.create(
            trip=trip,
            original_snapshot={"total_amount": "1000.00", "calculation_version": "v1"},
            original_total_amount=Decimal("1000.00"),
            proposed_total_amount=Decimal("900.00"),
            delta_amount=Decimal("-100.00"),
            reason="Approved customer recovery",
            requested_by=requester,
        )
        override.status = QuoteOverrideStatus.APPROVED
        override.reviewed_by = requester
        override.reviewed_at = timezone.now()
        with self.assertRaises(ValidationError):
            override.save()

    def test_quote_override_request_is_immutable(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        requester = get_user_model().objects.create_user(username="immutable-requester")
        trip = Trip.objects.create(
            customer_name="Direct customer",
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now() + datetime.timedelta(hours=3),
        )
        override = TripQuoteOverride.objects.create(
            trip=trip,
            original_snapshot={"total_amount": "1000.00"},
            original_total_amount=Decimal("1000.00"),
            proposed_total_amount=Decimal("900.00"),
            delta_amount=Decimal("-100.00"),
            reason="Customer recovery",
            requested_by=requester,
        )
        override.reason = "Changed later"
        with self.assertRaises(ValidationError):
            override.save()

    def test_driver_deletion_deletes_associated_user(self):
        from django.contrib.auth import get_user_model
        from fleet.models import Driver

        User = get_user_model()
        user = User.objects.create_user(username="driver_user_test", password="password123")
        driver = Driver.objects.create(
            user=user,
            name="Driver Test",
            phone="9999999999",
            license_number="DL-TEST-9999",
            home_base="Mumbai",
        )

        user_id = user.id
        driver_id = driver.id

        # Delete driver
        driver.delete()

        # Check driver is deleted
        self.assertFalse(Driver.objects.filter(id=driver_id).exists())

        # Check corresponding user is also deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())

